local predicate = 'process == "NotificationCenter" AND eventMessage CONTAINS "muted by display state (displayShared)"'
local pending
local activeAlert

local function recordingStatus()
  local app = hs.application.get("com.apple.controlcenter")
  if not app then return "Control Center is unavailable." end

  local menu = hs.axuielement.applicationElement(app).AXExtrasMenuBar
  for _, item in ipairs(menu and menu.AXChildren or {}) do
    if item.AXIdentifier == "com.apple.menuextra.controlcenter" then
      local description = item.AXDescription or ""
      if description:find("Screen Recording is in use", 1, true)
        or description:find("Bildschirmaufnahme wird verwendet", 1, true) then
        return "Control Center currently reports screen recording."
      end
    end
  end
  return "Current screen recording is unconfirmed."
end

local function showResult(exitCode, output)
  pending = nil
  local lastBlocked
  for timestamp in output:gmatch("(%d%d%d%d%-%d%d%-%d%d %d%d:%d%d:%d%d)[^\n]*muted by display state %(displayShared%)") do
    lastBlocked = timestamp
  end

  local headline = "⚪ Notification suppression unconfirmed"
  local detail = "No matching suppression was logged in the last 15 minutes."
  if exitCode ~= 0 then
    detail = "Could not read the macOS notification log."
  elseif lastBlocked then
    headline = "❌ Notification suppressed while sharing the display"
    detail = "Last confirmed event: " .. lastBlocked .. "."
  end

  local screen = hs.screen.primaryScreen()
  for _, candidate in ipairs(hs.screen.allScreens()) do
    if candidate:name() == "DELL U3225QE" then
      screen = candidate
      break
    end
  end

  local message = headline .. "\n" .. detail .. "\n" .. recordingStatus()
    .. "\n\nSystem Settings → Notifications → When mirroring or sharing the display"
  if activeAlert then hs.alert.closeSpecific(activeAlert) end
  activeAlert = hs.alert.show(message, {textSize = 17}, screen, 15)
end

hs.hotkey.bind(HammerspoonConfig.hyper, "n", function()
  if pending then return end
  pending = hs.task.new("/usr/bin/log", showResult, {
    "show", "--last", "15m", "--style", "compact", "--predicate", predicate,
  })
  if not pending or not pending:start() then
    showResult(1, "")
  end
end)
