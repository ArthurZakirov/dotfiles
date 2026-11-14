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

local function row(label, value, detail)
  local mark = value == nil and "⚪" or (value and "✅" or "❌")
  return mark .. " " .. label .. (detail and (": " .. detail) or "")
end

local function showConfiguration(value, audio)
  checking = false
  local effect = hs.audiodevice.defaultEffectDevice()
  local lines = {"Sound & Notifications"}
  local function add(text) lines[#lines + 1] = text end
  local selected
  if audio and audio.outputKnown then
    selected = false
    for _, device in ipairs(audio.devices) do
      if device.selected then selected = true end
    end
  end
  add(row("Sound effects output", selected, effect and effect:name() or "Unknown"))
  add(row("Multi-Output Device exists", audio and #audio.devices > 0))

  local function appStatus(label)
    local app = hs.application.get("com.apple.systempreferences")
    if not app then return nil end
    local function find(element, depth)
      if depth == 0 then return nil end
      for _, text in ipairs({element.AXTitle or "", element.AXDescription or "", element.AXValue or ""}) do
        if type(text) == "string" then
          local summary = text:match("^" .. label .. "[,\n] +(.+)$")
          if summary == "Off" then return false end
          if summary and (summary:find("Desktop", 1, true) or summary:find("Sounds", 1, true)
            or summary:find("Badges", 1, true)) then return true end
        end
      end
      for _, child in ipairs(element.AXChildren or {}) do
        local result = find(child, depth - 1)
        if result ~= nil then return result end
      end
      return nil
    end
    for _, window in ipairs(hs.axuielement.applicationElement(app).AXWindows or {}) do
      local result = find(window, 16)
      if result ~= nil then return result end
    end
  end
  table.insert(lines, 2, row("Google Chrome", appStatus("Google Chrome"))
    .. "     │     " .. row("Slack", appStatus("Slack")))
  table.insert(lines, 3, "↓  Shared macOS settings  ↓")
  local scriptOK, alertVolume = hs.osascript.applescript("alert volume of (get volume settings)")
  add(row("Alert volume", scriptOK and tonumber(alertVolume) and tonumber(alertVolume) > 0,
    scriptOK and (tostring(alertVolume) .. "%") or "Unknown"))
  local startup = hs.execute("/usr/sbin/nvram StartupMute 2>/dev/null"):match("StartupMute%s+(%S+)")
  add(row("Play sound on startup", startup and startup ~= "%01", not startup and "Unknown" or nil))
  local sharing
  if value == "Allow Notifications" then sharing = true
  elseif value == "Notifications Off" then sharing = false end
  add(row("Notifications while sharing", sharing, value or "Unknown"))
  local outputs = {}
  for _, device in ipairs(audio and audio.devices or {}) do
    for _, name in ipairs(device.members) do
      outputs[#outputs + 1] = row(name, device.selected)
    end
  end
  if #outputs > 0 then
    add("↓  Audio outputs  ↓")
    add(table.concat(outputs, "     │     "))
  end
  show(table.concat(lines, "\n"))
end

hs.hotkey.bind(HammerspoonConfig.hyper, "n", function()
  if checking then return end
  checking = true
  hs.execute("/usr/bin/open " .. settingsURL)
  local value
  local deadline = hs.timer.secondsSinceEpoch() + 5
  hs.timer.waitUntil(function()
    value = sharingSetting()
    return value ~= nil or hs.timer.secondsSinceEpoch() >= deadline
  end, function()
    local swift = hs.task.new("/usr/bin/swift", function(code, output)
      local ok, audio = pcall(hs.json.decode, output)
      showConfiguration(value, code == 0 and ok and audio or nil)
    end, {hs.configdir .. "/bin/audio_notification_status.swift"})
    if not swift or not swift:start() then showConfiguration(value) end
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
