-- One context-aware shortcut from VS Code or a GitHub/Bitbucket browser page.
-- Search remains in find-gpt-session; the launcher never copies search logic.
local runningTask

local function openFromContext(sourceApp)
  if runningTask then
    hs.alert.show("Session search already running")
    return
  end

  local bundle = sourceApp and sourceApp:bundleID() or ""
  if bundle:match("^com%.microsoft%.VSCode") then
    -- VS Code knows the exact workspaceFolder; don't guess from a window title.
    -- This private binding runs the managed VS Code task with that path.
    hs.eventtap.keyStroke({ "ctrl", "alt", "cmd", "shift" }, "s", 0)
    return
  end

  local url = HammerspoonConfig.gitBrowserUrl(sourceApp)
  if type(url) ~= "string" or url == "" then
    hs.alert.show("Open a GitHub/Bitbucket PR or branch in Chrome, or a Git worktree in VS Code")
    return
  end

  local helper = os.getenv("HOME") .. "/.local/bin/find-gpt-session"
  runningTask = hs.task.new(helper, function(exitCode, stdout, stderr)
    runningTask = nil
    if exitCode ~= 0 then
      hs.alert.show("Session search/open incomplete; inspect find-gpt-session logs", 5)
      return
    end
    local count = tonumber(stdout:match("Requested (%d+) new Warp/Chrome tabs"))
    if count and count > 0 then
      hs.alert.show("Opening " .. tostring(count) .. " session tabs")
    else
      hs.alert.show("No verified sessions to open")
    end
  end, { "--open", "--context-url", url })
  if not runningTask then
    hs.alert.show("Cannot start find-gpt-session")
    return
  end
  local environment = runningTask:environment()
  environment.PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" .. (environment.PATH or "")
  runningTask:setEnvironment(environment)
  if not runningTask:start() then
    runningTask = nil
    hs.alert.show("Cannot launch session search")
  end
end

-- Reuses the existing hyper-key family. Option+Cmd+Space is reserved by
-- macOS Finder Search, so do not silently replace a system shortcut.
hs.hotkey.bind(HammerspoonConfig.hyper, "s", function()
  local source = hs.application.frontmostApplication()
  HammerspoonConfig.afterModsReleased(function()
    openFromContext(source)
  end)
end)
