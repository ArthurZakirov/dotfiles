-- One context-aware shortcut from VS Code or a GitHub/Bitbucket browser page.
-- Search remains in find-gpt-session; the launcher never copies search logic.
local runningTask
-- Runtime-only diagnostics; never store conversation text, IDs or URLs.
HammerspoonConfig.lastRelatedSessionOpen = { phase = "idle" }

-- The search and the hotkey are independent. An inaccessible Safari provider
-- must not make "no verified match" look like a broken keyboard shortcut.
local function feedback(result, exitCode)
  if type(result) ~= "table" then
    return "Session-Suche fehlgeschlagen (Exit " .. tostring(exitCode) .. ").", 0, "invalid-output"
  end

  local hits = tonumber(result.total) or 0
  local opened = type(result.opening) == "table" and
      type(result.opening.dispatched) == "table" and #result.opening.dispatched or 0
  local incomplete = type(result.incomplete_providers) == "table" and
      result.incomplete_providers or {}
  local safariIncomplete = false
  local codexIncomplete = false
  for _, provider in ipairs(incomplete) do
    if provider == "safari" then safariIncomplete = true end
    if provider == "codex" then codexIncomplete = true end
  end

  if opened > 0 then
    local plural = opened == 1 and " Session" or " Sessions"
    -- ChatGPT cloud-history coverage is inherently partial even when the
    -- browser found and opened a verified hit. That is not an open failure.
    local openingErrors = type(result.opening) == "table" and
        type(result.opening.errors) == "table" and result.opening.errors or {}
    if exitCode ~= 0 or #openingErrors > 0 then
      return tostring(opened) .. plural .. " geöffnet; weitere Treffer nicht verfügbar.",
        opened, "partial-open"
    end
    return tostring(opened) .. plural .. " geöffnet.", opened, "opened"
  end
  if hits > 0 then
    return "Treffer gefunden, aber keine verifizierte Session geöffnet.", 0, "unopenable"
  end
  if safariIncomplete and codexIncomplete then
    return "Codex- und ChatGPT-Suche derzeit nicht verfügbar.", 0, "provider-incomplete"
  end
  if safariIncomplete then
    return "Keine Codex-Session gefunden; ChatGPT-Suche derzeit nicht verfügbar.",
      0, "provider-incomplete"
  end
  if #incomplete > 0 then
    return "Keine Session bestätigt: mindestens eine Suche ist unvollständig.",
      0, "provider-incomplete"
  end
  if exitCode == 1 or exitCode == 0 then
    return "Keine passende Session gefunden.", 0, "no-matches"
  end
  return "Session-Suche fehlgeschlagen (Exit " .. tostring(exitCode) .. ").", 0, "failed"
end

-- Separate pure diagnostic entry point for automated Hammerspoon/Lua tests.
HammerspoonConfig.relatedSessionFeedback = feedback

local function openFromContext(sourceApp)
  if runningTask then
    HammerspoonConfig.lastRelatedSessionOpen = { phase = "busy" }
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
    local parsed, result = pcall(hs.json.decode, stdout or "")
    if not parsed then result = nil end
    local message, opened, status = feedback(result, exitCode)
    HammerspoonConfig.lastRelatedSessionOpen = {
      phase = "finished",
      exitCode = exitCode,
      found = type(result) == "table" and (tonumber(result.total) or 0) or 0,
      opened = opened,
      status = status,
      error = type(result) ~= "table" and "invalid-output"
        or (status == "provider-incomplete" and "search-incomplete" or ""),
    }
    hs.alert.show(message, opened > 0 and 3 or 6)
  end, { "--json", "--open", "--context-url", url })
  if not runningTask then
    HammerspoonConfig.lastRelatedSessionOpen = { phase = "construct_failed" }
    hs.alert.show("Cannot start find-gpt-session")
    return
  end
  local environment = runningTask:environment()
  environment.PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" .. (environment.PATH or "")
  runningTask:setEnvironment(environment)
  HammerspoonConfig.lastRelatedSessionOpen = { phase = "starting" }
  if not runningTask:start() then
    runningTask = nil
    HammerspoonConfig.lastRelatedSessionOpen = { phase = "start_failed" }
    hs.alert.show("Cannot launch session search")
  end
end

-- Explicit entrypoint for on-demand CLI/IPC diagnostics without synthetic hotkeys.
HammerspoonConfig.openRelatedSessionsFromApp = openFromContext

-- Reuses the existing hyper-key family. Option+Cmd+Space is reserved by
-- macOS Finder Search, so do not silently replace a system shortcut.
local function onSessionHotkey()
  local source = hs.application.frontmostApplication()
  -- Show acknowledgement on KEY DOWN, not after release. Waiting for
  -- checkKeyboardModifiers() caused a silent failure on real Chrome presses:
  -- the helper sometimes never observed all modifiers as released.
  HammerspoonConfig.lastRelatedSessionOpen = {
    phase = "hotkey-received",
    source = source and source:bundleID() or "unknown",
  }
  hs.alert.show("Session-Suche gestartet …", 1.0)

  -- Only VS Code needs the modifiers fully released before injecting its
  -- *different* task shortcut. Chrome performs no synthetic keystrokes.
  local bundle = source and source:bundleID() or ""
  if bundle:match("^com%.microsoft%.VSCode") then
    HammerspoonConfig.afterModsReleased(function()
      openFromContext(source)
    end)
  else
    openFromContext(source)
  end
end

HammerspoonConfig.openRelatedSessionsFromHotkey = onSessionHotkey
hs.hotkey.bind(HammerspoonConfig.hyper, "s", onSessionHotkey)
