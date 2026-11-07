-- LuaJIT host simulation for the real Hammerspoon module.
local config, scenario = arg[1], arg[2]
local sid = "01a19bba-ec2e-77d3-ac71-ef6b036b2ad8"
local clipboard = "original user content"
local version = 5
local clipboardWrites = 0
local injection = 0
local taskArguments
local task
local pending = {}
local statuses = {}
local appId = scenario == "wrong_app" and "com.apple.Terminal" or "com.openai.codex"
local originalFormats = { ["public.utf8-plain-text"] = clipboard }
local filenames = {}
local times = {}

local function runNext()
  local timer = table.remove(pending, 1)
  assert(timer, "expected a scheduled operation")
  timer.fn()
end

local function emulateCopy()
  injection = injection + 1
  if scenario == "no_link" then return end
  version = version + 1
  if scenario == "wrong_link" then
    clipboard = "a user clipboard change, not a Codex link"
  else
    clipboard = "codex://threads/" .. sid
  end
end

local app = { bundleID = function() return appId end }
_G.hs = {
  configdir = config,
  application = { frontmostApplication = function() return app end },
  hotkey = { bind = function(_, key, fn) assert(key == "f"); _G.trigger = fn end },
  fs = { attributes = function(path)
    if scenario == "checker_missing" and path:match("agents_md_pipeline$") then return nil end
    if scenario == "intel_homebrew" and path == "/opt/homebrew/bin/python3" then return nil end
    if scenario == "python_missing" and
        (path == "/opt/homebrew/bin/python3" or path == "/usr/local/bin/python3") then
      return nil
    end
    return "file"
  end },
  eventtap = { keyStroke = function(mods, key, delay, target)
    assert(key == "l" and target == app)
    emulateCopy()
  end },
  pasteboard = {
    allContentTypes = function()
      if scenario == "multi_clipboard" then return {{"a"},{"b"}} end
      return {{"public.utf8-plain-text"}}
    end,
    readAllData = function() return originalFormats end,
    changeCount = function() return version end,
    getContents = function() return clipboard end,
    clearContents = function() clipboard = ""; clipboardWrites = clipboardWrites + 1 end,
    writeAllData = function(data)
      assert(data == originalFormats)
      clipboard = data["public.utf8-plain-text"]
      clipboardWrites = clipboardWrites + 1
      return true
    end,
  },
  timer = { doAfter = function(_, fn)
    local x = {fn=fn,stop=function() end}
    table.insert(pending, x)
    return x
  end },
  task = {new = function(python, callback, args)
    assert(python == (scenario == "intel_homebrew" and "/usr/local/bin/python3"
      or "/opt/homebrew/bin/python3"))
    taskArguments = args
    task = {
      start = function() return true end,
      terminate = function() end,
      isRunning = function() return true end,
      callback = callback,
    }
    return task
  end},
  json = { decode = function(value)
    if value == "garbled" then error("not json") end
    local statusesByScenario = {
      current = {"current", "current", "current", "current", "current"},
      outdated = {"current", "current", "current", "current", "outdated"},
      no_snapshot = {"current", "current", "current", "current", "unknown"},
      local_stale = {"current", "outdated", "current", "current", "current"},
      deployed_stale = {"current", "current", "current", "outdated", "current"},
    }
    local states = statusesByScenario[value] or statusesByScenario.current
    local labels = {"GitHub main", "Lokales main", "Guidance erzeugt", "Chezmoi apply", "Codex-Kontext"}
    local stages = {}
    local overall = "current"
    for i, status in ipairs(states) do
      stages[i] = {label = labels[i], status = status, detail = "test detail"}
      if status == "outdated" then overall = "outdated"
      elseif status == "unknown" and overall ~= "outdated" then overall = "unknown" end
    end
    return {stages=stages,overall=overall}
  end },
  mouse = {getCurrentScreen = function() return {frame = function() return {x=0,y=0,w=1200,h=900} end} end},
  screen = {mainScreen = function() return {frame = function() return {x=0,y=0,w=1200,h=900} end} end},
  canvas = {
    windowLevels = {overlay=1},
    new = function()
      local canvas = {
        appendElements = function(self, ...)
          local elements = {...}
          local label = elements[2].text
          local icons = {}
          for i=3, #elements, 3 do icons[#icons+1] = elements[i].text end
          statuses[#statuses+1] = {label = label, icons = icons}
        end,
        level = function() end,
        show = function() end,
        delete = function() end,
      }
      return canvas
    end,
  },
}
_G.HammerspoonConfig = {hyper={"ctrl","alt","cmd"}}
HammerspoonConfig.codexDesktopSession = dofile(config .. "/modules/codex_desktop_session.lua")
dofile(config .. "/modules/agents_freshness.lua")
assert(HammerspoonConfig.agentsFreshness.run == trigger)

trigger()
assert(#statuses == (scenario == "wrong_app" and 1 or 0), "no intermediate overlay")
if scenario == "python_missing" then
  runNext()
  assert(statuses[1].label == "AGENTS.md · 0/5 aktuell")
  assert(not task)
elseif scenario == "wrong_app" then
  assert(statuses[1].label == "AGENTS.md · 0/5 aktuell")
  assert(not task)
elseif scenario == "checker_missing" then
  runNext()
  assert(statuses[1].label == "AGENTS.md · 0/5 aktuell")
  assert(not task)
elseif scenario == "multi_clipboard" then
  assert(injection == 0)
  assert(taskArguments[1]:match("agents_md_pipeline$"))
  assert(taskArguments[2] == nil)
  task.callback(0, "no_snapshot", "")
  assert(statuses[1].icons[5] == "?")
elseif scenario == "no_link" then
  for i=1, 15 do runNext() end
  assert(taskArguments[2] == nil)
  task.callback(0, "no_snapshot", "")
  assert(statuses[1].icons[5] == "?")
  assert(clipboard == "original user content")
elseif scenario == "wrong_link" then
  runNext()
  assert(taskArguments[2] == nil)
  task.callback(0, "no_snapshot", "")
  assert(statuses[1].icons[5] == "?")
  assert(clipboard == "a user clipboard change, not a Codex link")
  assert(clipboardWrites == 0)
else
  runNext()
  assert(#statuses == 0, "no intermediate UI while subprocess runs")
  assert(clipboard == "original user content")
  assert(clipboardWrites == 1)
  assert(taskArguments[1]:match("agents_md_pipeline$"))
  assert(taskArguments[2] == "--session-id" and taskArguments[3] == sid)
  if scenario == "intel_homebrew" then
    task.callback(0, "current", "")
    assert(statuses[1].label == "AGENTS.md · 5/5 aktuell")
  elseif scenario == "current" then
    task.callback(0, "current", "")
    assert(statuses[1].label == "AGENTS.md · 5/5 aktuell")
    assert(table.concat(statuses[1].icons) == "✓✓✓✓✓")
  elseif scenario == "outdated" then
    task.callback(0, "outdated", "")
    assert(statuses[1].label == "AGENTS.md · 4/5 aktuell")
    assert(table.concat(statuses[1].icons) == "✓✓✓✓✕")
  elseif scenario == "local_stale" then
    task.callback(0, "local_stale", "")
    assert(table.concat(statuses[1].icons) == "✓✕✓✓✓")
  elseif scenario == "deployed_stale" then
    task.callback(0, "deployed_stale", "")
    assert(table.concat(statuses[1].icons) == "✓✓✓✕✓")
  elseif scenario == "no_snapshot" then
    task.callback(0, "no_snapshot", "")
    assert(table.concat(statuses[1].icons) == "✓✓✓✓?")
  elseif scenario == "corrupt_json" then
    task.callback(0, "garbled", "")
    assert(statuses[1].label == "AGENTS.md · 0/5 aktuell")
  elseif scenario == "checker_error" then
    task.callback(1, "", "bad exit")
    assert(statuses[1].label == "AGENTS.md · 0/5 aktuell")
  end
end
print("PASS " .. scenario)
