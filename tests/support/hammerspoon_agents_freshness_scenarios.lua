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
  application = { frontmostApplication = function() return app end },
  hotkey = { bind = function(_, key, fn) assert(key == "f"); _G.trigger = fn end },
  fs = { attributes = function(path)
    if scenario == "checker_missing" and path:match("check.py$") then return nil end
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
    assert(python == "/opt/homebrew/bin/python3")
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
    return {status=value,session_id=sid,seen_source_digest="abc",current_source_digest="def"}
  end },
  mouse = {getCurrentScreen = function() return {frame = function() return {x=0,y=0,w=1200,h=900} end} end},
  screen = {mainScreen = function() return {frame = function() return {x=0,y=0,w=1200,h=900} end} end},
  canvas = {
    windowLevels = {overlay=1},
    new = function()
      local canvas = {
        appendElements = function(self, ...)
          local elements = {...}
          statuses[#statuses+1] = elements[3].text
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
dofile(config .. "/modules/agents_freshness.lua")
assert(HammerspoonConfig.agentsFreshness.run == trigger)

trigger()
-- The hotkey does not render a temporary blue checking card.
if scenario ~= "wrong_app" and scenario ~= "multi_clipboard" then
  assert(#statuses == 0, "must wait for a verified result before displaying")
end
if scenario == "wrong_app" or scenario == "multi_clipboard" or scenario == "checker_missing" then
  if scenario == "checker_missing" then runNext() end
  assert(injection == (scenario == "checker_missing" and 1 or 0))
  assert(statuses[#statuses] == "AGENTS.md not verified")
  assert(not task)
elseif scenario == "no_link" then
  for i=1,15 do runNext() end
  assert(statuses[#statuses] == "AGENTS.md not verified")
  assert(not task and clipboard == "original user content")
elseif scenario == "wrong_link" then
  runNext()
  assert(statuses[#statuses] == "AGENTS.md not verified")
  assert(clipboard == "a user clipboard change, not a Codex link")
  assert(clipboardWrites == 0)
else
  runNext()
  assert(#statuses == 0, "clipboard capture must not show an intermediate card")
  assert(clipboard == "original user content")
  assert(clipboardWrites == 1)
  assert(taskArguments[1]:match("check.py$"))
  assert(taskArguments[2] == "--check" and taskArguments[3] == "--session-id")
  assert(taskArguments[4] == sid)
  if scenario == "current" then
    task.callback(0, "current", "")
    assert(statuses[#statuses] == "AGENTS.md current")
  elseif scenario == "outdated" then
    task.callback(0, "outdated", "")
    assert(statuses[#statuses] == "AGENTS.md outdated")
  elseif scenario == "no_snapshot" then
    task.callback(0, "unknown", "")
    assert(statuses[#statuses] == "AGENTS.md not verified")
  elseif scenario == "corrupt_json" then
    task.callback(0, "garbled", "")
    assert(statuses[#statuses] == "AGENTS.md not verified")
  elseif scenario == "checker_error" then
    task.callback(1, "", "bad exit")
    assert(statuses[#statuses] == "AGENTS.md not verified")
  end
end
print("PASS " .. scenario)
