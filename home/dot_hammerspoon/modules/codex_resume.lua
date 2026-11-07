-- Ctrl+Alt+Cmd+W: resume the exact foreground Codex desktop thread in Warp.
local M = {}
local SCRIPT = hs.configdir .. "/bin/codex_resume_warp"
local inFlight = false
local cancelCapture
local launchTask

local function finish(message)
  inFlight = false
  cancelCapture = nil
  launchTask = nil
  if message then hs.alert.show(message, 4) end
end

-- Quit only the originally captured Desktop process, never whichever app is now
-- frontmost (which will normally be Warp by the time its tab has started).
local function quitDesktopAfterWarpReady(app)
  if not HammerspoonConfig.codexDesktopSession.isDesktopApp(app) then
    finish("Codex Desktop konnte nicht zugeordnet werden")
    return
  end
  if app:isRunning() then
    local ok, err = pcall(function() app:kill() end)
    if not ok then
      hs.printf("Codex Desktop graceful quit failed: %s", tostring(err))
      finish("Codex Desktop konnte nicht beendet werden")
      return
    end
  end
  local checks = 0
  local function verifyExit()
    if not app:isRunning() then
      finish("Desktop beendet; Codex setzt in Warp fort")
      return
    end
    checks = checks + 1
    if checks >= 60 then
      finish("Desktop noch geöffnet: Codex-Session wartet in Warp")
      return
    end
    hs.timer.doAfter(0.25, verifyExit)
  end
  verifyExit()
end

local function openInWarp(sessionId, desktopApp)
  if not hs.fs.attributes(SCRIPT, "mode") then
    finish("Codex Warp launcher fehlt")
    return
  end
  local task = hs.task.new(SCRIPT, function(exitCode, stdout, stderr)
    if exitCode ~= 0 then
      hs.printf("Codex Warp launch failed: %s", stderr or "")
      finish("Warp-Tab konnte nicht geöffnet werden")
    else
      quitDesktopAfterWarpReady(desktopApp)
    end
  end, { "--session-id", sessionId })
  if not task then
    finish("Codex Warp launcher konnte nicht starten")
    return
  end
  local env = task:environment()
  env.PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" .. (env.PATH or "")
  task:setEnvironment(env)
  launchTask = task
  if not task:start() then
    finish("Codex Warp launcher konnte nicht starten")
  end
end

function M.run()
  if inFlight then
    hs.alert.show("Codex-Session wird bereits geöffnet")
    return
  end
  local app = hs.application.frontmostApplication()
  if not HammerspoonConfig.codexDesktopSession.isDesktopApp(app) then
    hs.alert.show("Codex Desktop öffnen")
    return
  end
  inFlight = true
  HammerspoonConfig.afterModsReleased(function()
    cancelCapture = HammerspoonConfig.codexDesktopSession.capture(app, function(sessionId, problem)
      cancelCapture = nil
      if not sessionId then
        finish("Keine Codex-Session-ID: " .. (problem or "unbekannt"))
        return
      end
      openInWarp(sessionId, app)
    end)
  end)
end

hs.hotkey.bind(HammerspoonConfig.hyper, "w", M.run)
HammerspoonConfig.codexResume = M
return M
