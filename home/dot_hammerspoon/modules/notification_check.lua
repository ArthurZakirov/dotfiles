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

local statusCard
local closeTimer
local function showCard(sources, settings, outputs)
  if statusCard then statusCard:delete() end
  if closeTimer then closeTimer:stop() end
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
  closeTimer = hs.timer.doAfter(15, function()
    if statusCard then statusCard:delete(); statusCard = nil end
    closeTimer = nil
  end)
end

local function showConfiguration(value, audio, appStates)
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
  local startup = hs.execute("/usr/sbin/nvram StartupMute 2>/dev/null"):match("StartupMute%s+(%S+)")
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
    {label="Play sound on startup", icon="⏻", value=startup and startup ~= "%01"},
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
  showCard(sources, settings, outputs)
end

local function waitForSetting(read, done)
  local value
  local deadline = hs.timer.secondsSinceEpoch() + 4
  hs.timer.waitUntil(function()
    value = read()
    return value ~= nil or hs.timer.secondsSinceEpoch() >= deadline
  end, function() done(value) end, 0.2)
end

local function appToggle(title)
  local function find(element, depth)
    if depth == 0 then return nil end
    if element.AXIdentifier == "allow-notifications" then return element.AXValue end
    for _, child in ipairs(element.AXChildren or {}) do
      local value = find(child, depth - 1)
      if value ~= nil then return value end
    end
  end
  local app = hs.application.get("com.apple.systempreferences")
  if not app then return nil end
  for _, window in ipairs(hs.axuielement.applicationElement(app).AXWindows or {}) do
    if window.AXTitle == title then
      local value = find(window, 16)
      if value == 0 or value == false then return false end
      if value == 1 or value == true then return true end
    end
  end
end

local function readApp(bundle, title, done)
  hs.execute("/usr/bin/open " .. string.format("%q", settingsURL .. "?id=" .. bundle))
  waitForSetting(function() return appToggle(title) end, done)
end

hs.hotkey.bind(HammerspoonConfig.hyper, "n", function()
  if checking then return end
  checking = true
  readApp("com.google.Chrome", "Google Chrome", function(chrome)
    readApp("com.tinyspeck.slackmacgap", "Slack", function(slack)
      hs.execute("/usr/bin/open " .. settingsURL)
      waitForSetting(sharingSetting, function(value)
        local states = {chrome = chrome, slack = slack}
        local swift = hs.task.new("/usr/bin/swift", function(code, output)
          local ok, audio = pcall(hs.json.decode, output)
          showConfiguration(value, code == 0 and ok and audio or nil, states)
        end, {hs.configdir .. "/bin/audio_notification_status.swift"})
        if not swift or not swift:start() then showConfiguration(value, nil, states) end
      end)
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
