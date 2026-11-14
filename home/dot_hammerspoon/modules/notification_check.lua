local settingsURL = "x-apple.systempreferences:com.apple.Notifications-Settings.extension"
local predicate = 'process == "NotificationCenter" AND eventMessage CONTAINS "muted by display state (displayShared)"'
local activeAlert
local checking = false
local stream
local retryTimer

local function show(message)
  local screen = hs.screen.primaryScreen()
  for _, candidate in ipairs(hs.screen.allScreens()) do
    if candidate:name() == "DELL U3225QE" then
      screen = candidate
      break
    end
  end
  if activeAlert then hs.alert.closeSpecific(activeAlert) end
  activeAlert = hs.alert.show(message, {textSize = 17}, screen, 15)
end

local function findSharingSetting(element, depth)
  if not element or depth == 0 then return nil end
  if element.AXIdentifier == "allow-when-sharing" then
    return element.AXValue
  end
  for _, child in ipairs(element.AXChildren or {}) do
    local value = findSharingSetting(child, depth - 1)
    if value then return value end
  end
end

local function sharingSetting()
  local app = hs.application.get("com.apple.systempreferences")
  if not app then return nil end
  local settings = hs.axuielement.applicationElement(app)
  for _, window in ipairs(settings.AXWindows or {}) do
    local value = findSharingSetting(window, 16)
    if value then return value end
  end
end

local function showConfiguration(value)
  checking = false
  if value == "Allow Notifications" then
    show("✅ Notifications are allowed while mirroring or sharing the display.")
  elseif value == "Notifications Off" then
    show("❌ Notifications are off while mirroring or sharing the display.\n"
      .. "System Settings → Notifications → When mirroring or sharing the display → Allow Notifications")
  else
    show("⚪ Could not verify the current display-sharing notification setting.\n"
      .. "System Settings → Notifications → When mirroring or sharing the display")
  end
end

hs.hotkey.bind(HammerspoonConfig.hyper, "n", function()
  if checking then return end
  local value = sharingSetting()
  if value then
    showConfiguration(value)
    return
  end

  checking = true
  hs.execute("/usr/bin/open " .. settingsURL)
  local deadline = hs.timer.secondsSinceEpoch() + 5
  hs.timer.waitUntil(function()
    value = sharingSetting()
    return value ~= nil or hs.timer.secondsSinceEpoch() >= deadline
  end, function()
    showConfiguration(value)
  end, 0.25)
end)

local function watchSuppressions()
  local buffer = ""
  local lastWarning = 0
  stream = hs.task.new("/usr/bin/log", function()
    stream = nil
    retryTimer = hs.timer.doAfter(5, watchSuppressions)
  end, function(task, output)
    if not task then return false end
    buffer = buffer .. output
    local lineEnd = buffer:match(".*()\n")
    if not lineEnd then return true end

    local lines = buffer:sub(1, lineEnd)
    buffer = buffer:sub(lineEnd + 1)
    local now = hs.timer.secondsSinceEpoch()
    if lines:find("muted by display state (displayShared)", 1, true) and now - lastWarning >= 3 then
      lastWarning = now
      show("⚠️ A notification was just suppressed while sharing the display.\n"
        .. "Press Control + Option + Command + N to check the current setting.")
    end
    return true
  end, {"stream", "--style", "compact", "--predicate", predicate})

  if not stream or not stream:start() then
    retryTimer = hs.timer.doAfter(5, watchSuppressions)
  end
end

watchSuppressions()
