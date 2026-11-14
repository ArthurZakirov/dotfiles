local settingsURL = "x-apple.systempreferences:com.apple.Notifications-Settings.extension"
local predicate = 'process == "NotificationCenter" AND eventMessage CONTAINS "muted by display state (displayShared)"'
local activeAlert
local checking = false
local stream
local retryTimer

local function targetScreen()
  local screen = hs.screen.primaryScreen()
  for _, candidate in ipairs(hs.screen.allScreens()) do
    if candidate:name() == "DELL U3225QE" then
      screen = candidate
      break
    end
  end
  return screen
end

local function show(message)
  if activeAlert then hs.alert.closeSpecific(activeAlert) end
  activeAlert = hs.alert.show(message, {textSize = 17}, targetScreen(), 15)
end

local function settingsControl(title, identifier)
  local function find(element, depth)
    if depth == 0 then return nil end
    if element.AXIdentifier == identifier then return element end
    for _, child in ipairs(element.AXChildren or {}) do
      local value = find(child, depth - 1)
      if value ~= nil then return value end
    end
  end
  local app = hs.application.get("com.apple.systempreferences")
  if not app then return nil end
  for _, window in ipairs(hs.axuielement.applicationElement(app).AXWindows or {}) do
    if title == nil or window.AXTitle == title then
      local value = find(window, 20)
      if value ~= nil then return value end
    end
  end
end

local function settingsValue(title, identifier)
  local control = settingsControl(title, identifier)
  return control and control.AXValue
end

local function checkbox(title, identifier)
  local value = settingsValue(title, identifier)
  if value == 0 or value == false then return false end
  if value == 1 or value == true then return true end
end

local function sharingSetting()
  local value = settingsValue(nil, "allow-when-sharing")
  if value == "Allow Notifications" or value == "Notifications Off" then return value end
end

local statusCard
local closeTimer
local escapeHotkey

local function closeCard()
  if closeTimer then closeTimer:stop(); closeTimer = nil end
  if escapeHotkey then escapeHotkey:delete(); escapeHotkey = nil end
  if statusCard then statusCard:delete(); statusCard = nil end
end

local function showCard(sources, settings, outputs)
  closeCard()
  local frame = targetScreen():frame()
  local width, gap = math.min(frame.w - 32, 600), 12
  local height = 358 + math.max(1, math.ceil(#outputs / 2)) * 36
  statusCard = hs.canvas.new({x = frame.x + (frame.w - width) / 2,
    y = frame.y + math.max(0, (frame.h - height) / 2), w = width, h = height})
  statusCard:level(hs.canvas.windowLevels.overlay)
  local function box(x,y,w,h,color)
    statusCard:appendElements({type="rectangle", action="fill", roundedRectRadii={xRadius=12,yRadius=12},
      fillColor=color, frame={x=x,y=y,w=w,h=h}})
  end
  local function text(value,x,y,w,size,color)
    statusCard:appendElements({type="text",text=value,textSize=size,textColor=color or {white=0.95},
      frame={x=x,y=y,w=w,h=28}})
  end
  local function entry(item,x,y,w)
    local image = item.bundle and hs.image.imageFromAppBundle(item.bundle)
    if image then
      statusCard:appendElements({type="image",image=image,frame={x=x,y=y,w=24,h=24}})
    else
      text(item.icon or "🔊",x,y,27,16)
    end
    text(item.label,x+32,y+2,w-60,14)
    local status = item.value == nil and "—" or (item.value and "✓" or "✕")
    local color = item.value == nil and {white=0.6} or
      (item.value and {red=0.40,green=0.88,blue=0.64} or {red=1,green=0.45,blue=0.46})
    text(status,x+w-23,y,24,18,color)
  end
  local tone = {white=0.16}
  local sectionWidth = width - 32
  local half = (sectionWidth - 32 - gap) / 2
  box(0,0,width,height,{white=0.09,alpha=0.98})
  text("Sound & Notifications",20,14,width-40,20)
  box(16,50,sectionWidth,82,tone)
  text("Notification sources",30,60,sectionWidth-28,15)
  for i, item in ipairs(sources) do entry(item,32+(i-1)*(half+gap),93,half) end
  box(16,144,sectionWidth,174,tone)
  text("Shared macOS settings",30,154,sectionWidth-28,15)
  for i, item in ipairs(settings) do entry(item,32,178+(i-1)*26,sectionWidth-32) end
  box(16,330,sectionWidth,height-338,tone)
  text("Audio outputs",30,336,sectionWidth-28,15)
  if #outputs == 0 then text("No output members verified",32,360,sectionWidth-32,14) end
  for i, item in ipairs(outputs) do
    entry(item,32+((i-1)%2)*(half+gap),360+math.floor((i-1)/2)*36,half)
  end
  statusCard:show()
  escapeHotkey = hs.hotkey.bind({}, "escape", closeCard)
  closeTimer = hs.timer.doAfter(15, closeCard)
end

local function showConfiguration(value, audio, appStates, startup)
  checking = false
  local effect = hs.audiodevice.defaultEffectDevice()
  local selected
  if audio and audio.outputKnown then
    selected = false
    for _, device in ipairs(audio.devices) do
      if device.selected then selected = true end
    end
  end
  local ok, rawVolume = hs.osascript.applescript("alert volume of (get volume settings)")
  local volume = ok and tonumber(rawVolume) or nil
  local sharing
  if value == "Allow Notifications" then sharing = true
  elseif value == "Notifications Off" then sharing = false end
  local sources = {
    {label="Google Chrome", bundle="com.google.Chrome", value=appStates.chrome},
    {label="Slack", bundle="com.tinyspeck.slackmacgap", value=appStates.slack},
  }
  local settings = {
    {label="Notifications while sharing", icon="🖥", value=sharing},
    {label="Alert volume" .. (volume and (" · " .. volume .. "%") or ""),
      icon="🔔", value=volume and volume > 0},
    {label="Play sound on startup", icon="⏻", value=startup},
    {label="Multi-Output Device exists", icon="🎛", value=audio and #audio.devices > 0},
    {label="Sound effects output · " .. (effect and effect:name() or "Unknown"), icon="🔊", value=selected},
  }
  local outputs = {}
  for _, device in ipairs(audio and audio.devices or {}) do
    for _, name in ipairs(device.members) do
      outputs[#outputs + 1] = {label=name, value=device.selected,
        icon=name:find("Speaker",1,true) and "🔊" or "🎧"}
    end
  end
  if activeAlert then hs.alert.closeSpecific(activeAlert); activeAlert = nil end
  local rendered, err = pcall(showCard, sources, settings, outputs)
  if rendered then print("Notification diagnostics sharing: " .. tostring(value)) end
  if not rendered then
    print("Notification card: " .. tostring(err))
    show("Sound & Notifications: could not render the status card.")
  end
end

local function waitForSetting(read, done, timeout)
  local value
  local deadline = hs.timer.secondsSinceEpoch() + (timeout or 4)
  hs.timer.waitUntil(function()
    value = read()
    return value ~= nil or hs.timer.secondsSinceEpoch() >= deadline
  end, function() done(value) end, 0.2)
end

local function openSettings(url, done)
  local task = hs.task.new("/usr/bin/open", function(code)
    done(code == 0)
  end, {url})
  if not task or not task:start() then done(false) end
end

local function readSetting(url, read, done)
  openSettings(url, function(opened)
    if opened then waitForSetting(read, done)
    else done(nil) end
  end)
end

local function readApp(bundle, title, done)
  readSetting(settingsURL .. "?id=" .. bundle, function()
    return checkbox(title, "allow-notifications")
  end, done)
end

hs.hotkey.bind(HammerspoonConfig.hyper, "n", function()
  if checking then return end
  checking = true
  show("Checking Sound & Notifications…")
  readSetting("x-apple.systempreferences:com.apple.Sound-Settings.extension", function()
    return checkbox("Sound", "BootChimeCheckbox")
  end, function(startup)
    local backPressed = false
    local function readSharing()
      local value = sharingSetting()
      if value ~= nil then return value end
      if not backPressed then
        local back = settingsControl("Slack", "go back") or settingsControl("Google Chrome", "go back")
        if back then backPressed = not not back:performAction("AXPress") end
      end
    end
    local function withSharing(value)
      readApp("com.google.Chrome", "Google Chrome", function(chrome)
        readApp("com.tinyspeck.slackmacgap", "Slack", function(slack)
          local back = settingsControl("Slack", "go back") or settingsControl("Google Chrome", "go back")
          if back then back:performAction("AXPress") end
          local states = {chrome = chrome, slack = slack}
          local swift = hs.task.new("/usr/bin/swift", function(code, output)
            local ok, audio = pcall(hs.json.decode, output)
            showConfiguration(value, code == 0 and ok and audio or nil, states, startup)
          end, {hs.configdir .. "/bin/audio_notification_status.swift"})
          if not swift or not swift:start() then showConfiguration(value, nil, states, startup) end
        end)
      end)
    end
    openSettings(settingsURL, function(opened)
      if not opened then withSharing(nil); return end
      waitForSetting(readSharing, function(value)
        if value ~= nil then withSharing(value); return end
        backPressed = false
        openSettings(settingsURL, function(reopened)
          if reopened then waitForSetting(readSharing, withSharing, 6)
          else withSharing(nil) end
        end)
      end, 6)
    end)
  end)
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
