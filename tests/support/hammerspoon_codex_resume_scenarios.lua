-- Simulated Hammerspoon hotkey tests: clipboard, ID extraction and launch contract.
local directory, scenario = arg[1], arg[2]
local sid = "01a19bba-ec2e-77d3-ac71-ef6b036b2ad8"
local original = "keep clipboard"
local clipboard = original
local old = { ["public.utf8-plain-text"] = original }
local counter, writes, copies = 4, 0, 0
local queued = {}
local launchArgs, task, message
local appRunning, quitCount, exitPolls = true, 0, 0
local app = {
  bundleID = function()
    return scenario == "wrong_app" and "com.apple.Terminal" or "com.openai.codex"
  end,
  isRunning = function()
    if scenario == "quit_delayed" and quitCount > 0 then
      exitPolls = exitPolls + 1
      if exitPolls >= 3 then appRunning = false end
    end
    return appRunning
  end,
  kill = function()
    quitCount = quitCount + 1
    if scenario ~= "quit_refused" and scenario ~= "quit_delayed" then
      appRunning = false
    end
  end,
}

local function pump()
  local event = table.remove(queued, 1)
  assert(event, "expected pending timer")
  if not event.stopped then event.fn() end
end

_G.hs = {
  configdir = directory,
  application = { frontmostApplication = function() return app end },
  hotkey = { bind = function(_, key, fn)
    assert(key == "w"); _G.trigger = fn
  end },
  alert = { show = function(text) message = text end },
  printf = function() end,
  fs = { attributes = function()
    if scenario == "missing_launcher" then return nil end
    return "file"
  end },
  eventtap = { keyStroke = function(mods, key, delay, target)
    assert(mods[1] == "cmd" and mods[2] == "alt")
    assert(key == "l" and target == app)
    copies = copies + 1
    if scenario == "no_link" then return end
    counter = counter + 1
    clipboard = scenario == "invalid_link" and "https://example.com" or "codex://threads/" .. sid
  end },
  pasteboard = {
    allContentTypes = function()
      if scenario == "multi_clipboard" then return {{"first"}, {"second"}} end
      return {{"public.utf8-plain-text"}}
    end,
    readAllData = function() return old end,
    changeCount = function() return counter end,
    getContents = function() return clipboard end,
    writeAllData = function(content)
      assert(content == old)
      clipboard = original; writes = writes + 1
    end,
    clearContents = function() clipboard = ""; writes = writes + 1 end,
  },
  timer = { doAfter = function(_, fn)
    local timer = {fn=fn,stop=function(self) self.stopped=true end}
    queued[#queued+1] = timer
    return timer
  end },
  task = {new = function(path, callback, argv)
    assert(path == directory .. "/bin/codex_resume_warp")
    launchArgs = argv
    task = {
      environment = function() return {PATH="/usr/bin"} end,
      setEnvironment = function(self, env) assert(env.PATH:find("/opt/homebrew/bin",1,true)) end,
      start = function(self)
        if scenario == "task_fails_start" then return false end
        return true
      end,
      callback = callback,
    }
    return task
  end},
}
_G.HammerspoonConfig = {
  hyper = {"ctrl", "alt", "cmd"},
  afterModsReleased = function(callback) callback() end,
}
HammerspoonConfig.codexDesktopSession = dofile(directory .. "/modules/codex_desktop_session.lua")
dofile(directory .. "/modules/codex_resume.lua")
trigger()
if scenario == "overlap" then
  local rejection
  local noop = HammerspoonConfig.codexDesktopSession.capture(app, function(id, reason)
    assert(id == nil)
    rejection = reason
  end)
  assert(rejection == "Codex session capture already in progress")
  noop()
end
if scenario == "wrong_app" then
  assert(copies == 0 and not task)
  assert(message == "Codex Desktop öffnen")
elseif scenario == "multi_clipboard" then
  assert(copies == 0 and not task and clipboard == original)
elseif scenario == "no_link" then
  for i=1,15 do pump() end
  assert(not task and clipboard == original)
elseif scenario == "invalid_link" then
  pump()
  assert(not task and clipboard == "https://example.com" and writes == 0)
else
  pump()
  assert(copies == 1 and writes == 1 and clipboard == original)
  if scenario == "missing_launcher" then
    assert(not task and message == "Codex Warp launcher fehlt")
  else
    assert(task)
    assert(launchArgs[1] == "--session-id" and launchArgs[2] == sid)
    if scenario == "task_fails_start" then
      assert(message == "Codex Warp launcher konnte nicht starten")
    else
      -- Parent task returns success only once the Warp tab signals readiness.
      if scenario == "already_closed" then appRunning = false end
      task.callback(scenario == "task_returns_error" and 1 or 0, "", "failed")
      if scenario == "task_returns_error" then
        assert(message == "Warp-Tab konnte nicht geöffnet werden" and quitCount == 0)
      else
        if scenario == "quit_delayed" then
          pump(); pump()
        elseif scenario == "quit_refused" then
          for i=1,59 do pump() end
        end
        if scenario == "quit_refused" then
          assert(message == "Desktop noch geöffnet: Codex-Session wartet in Warp")
        else
          assert(message == "Desktop beendet; Codex setzt in Warp fort")
        end
        assert(quitCount == (scenario == "already_closed" and 0 or 1))
      end
    end
  end
end
print("PASS " .. scenario)
