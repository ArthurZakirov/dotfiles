local settingsURL = "x-apple.systempreferences:com.apple.Notifications-Settings.extension"
local activeAlert
local checking = false

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

local function chromeSources()
  local home = os.getenv("HOME")
  local root = home .. "/Library/Application Support/Google/Chrome/"
  local ok, state = pcall(hs.json.read, root .. "Local State")
  local profile = ok and state and state.profile and state.profile.last_used
  local preferences
  if type(profile) == "string" and not profile:find("/", 1, true) then
    local read, data = pcall(hs.json.read, root .. profile .. "/Preferences")
    preferences = read and data and data.profile
  end
  local defaults = preferences and preferences.default_content_setting_values or {}
  local content = preferences and preferences.content_settings or {}
  local exceptions = content.exceptions and content.exceptions.notifications or {}
  local function site(label, host, subdomains)
    local allowed
    if preferences then
      allowed = false
      for pattern, rule in pairs(exceptions) do
        local origin = pattern:match("^https://([^/,:]+):?%d*,%*$")
        if origin and (origin == host or (subdomains and origin:sub(-#host-1) == "." .. host)) then
          if rule.setting == 1 then allowed = true; break end
        end
      end
      if not subdomains then
        local exact = exceptions["https://" .. host .. ":443,*"] or exceptions["https://" .. host .. ",*"]
        if not exact then allowed = defaults.notifications == 1 end
      end
    end
    return {label=label, bundle="com.google.Chrome", value=allowed}
  end
  return {
    site("Google Calendar", "calendar.google.com"),
    site("Gmail", "mail.google.com"),
    site("Slack · Chrome", "slack.com", true),
    site("ChatGPT · Chrome", "chatgpt.com"),
  }
end

local function showCard(sources, permissions, settings, outputs)
  closeCard()
  local frame = targetScreen():frame()
  local width, gap = math.min(frame.w - 32, 600), 12
  local sourceHeight = 48 + math.max(#sources[1].items, #sources[2].items) * 26
  local permissionsY = 50 + sourceHeight + 12
  local settingsY = permissionsY + 88
  local outputsY = settingsY + 186
  local height = outputsY + 28 + math.max(1, math.ceil(#outputs / 2)) * 36
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
  local columnWidth = (sectionWidth - gap) / 2
  for i, source in ipairs(sources) do
    local x = 16 + (i - 1) * (columnWidth + gap)
    box(x, 50, columnWidth, sourceHeight, tone)
    text(source.title, x + 14, 60, columnWidth - 28, 15)
    for j, item in ipairs(source.items) do
      entry(item, x + 14, 90 + (j - 1) * 26, columnWidth - 28)
    end
  end
  box(16, permissionsY, sectionWidth, 76, tone)
  text("macOS app permissions", 30, permissionsY + 10, sectionWidth - 28, 15)
  for i, item in ipairs(permissions) do
    entry(item, 32 + (i - 1) * (half + gap), permissionsY + 40, half)
  end
  box(16, settingsY, sectionWidth, 174, tone)
  text("Shared macOS settings", 30, settingsY + 10, sectionWidth - 28, 15)
  for i, item in ipairs(settings) do entry(item, 32, settingsY + 34 + (i - 1) * 26, sectionWidth - 32) end
  box(16, outputsY, sectionWidth, height - outputsY - 8, tone)
  text("Audio outputs", 30, outputsY + 6, sectionWidth - 28, 15)
  if #outputs == 0 then text("No output members verified", 32, outputsY + 30, sectionWidth - 32, 14) end
  for i, item in ipairs(outputs) do
    entry(item, 32 + ((i - 1) % 2) * (half + gap), outputsY + 30 + math.floor((i - 1) / 2) * 36, half)
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
  local prefs = appStates.slackPreferences or {}
  local mentions = "Mentions and Direct Messages"
  local function modeSelected(label)
    if prefs.mode == "Everything" or (type(prefs.mode) == "string" and prefs.mode:lower() == mentions:lower()) then
      return prefs.mode:lower() == label:lower()
    end
  end
  local sources = {
    {title="Chrome website notifications", items=chromeSources()},
    {title="Slack in-app notifications", items={
      {label="Slack · In-app", bundle="com.tinyspeck.slackmacgap", value=appStates.slackInApp},
      {label="Desktop notifications", icon="🖥", value=prefs.desktop},
      {label="Everything", icon="🔔", value=modeSelected("Everything")},
      {label="Mentions and DMs", icon="💬", value=modeSelected(mentions)},
      {label="Thread replies", icon="↩", value=prefs.threads},
      {label="Messages from VIPs", icon="★", value=prefs.vips},
    }},
  }
  local permissions = {
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
  local rendered, err = pcall(showCard, sources, permissions, settings, outputs)
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

local function slackElement(root, matches)
  local queue = {root}
  for i = 1, 3500 do
    local element = queue[i]
    if not element then return end
    local role = element:attributeValue("AXRole")
    for _, attribute in ipairs({"AXTitle", "AXDescription", "AXValue"}) do
      local label = element:attributeValue(attribute)
      if type(label) == "string" and matches(label, role) then return element, label end
    end
    for _, child in ipairs(element:attributeValue("AXChildren") or {}) do
      queue[#queue+1] = child
    end
  end
end

local function readSlackPreferences(app, done)
  local function control(title, role)
    return slackElement(hs.axuielement.applicationElement(app), function(label, kind)
      return kind == role and (not title or label == title)
    end)
  end
  local function checked(title)
    local element = control(title, "AXCheckBox")
    local value = element and element:attributeValue("AXValue")
    if value == 0 or value == 1 then return value == 1 end
  end
  local alreadyOpen = control("Preferences", "AXHeading") ~= nil
  if not alreadyOpen then hs.eventtap.keyStroke({"cmd"}, ",", 0, app) end
  waitForSetting(function()
    if not app:isFrontmost() then return end
    local tab = control("Notifications", "AXRadioButton")
    if not tab then return end
    if tab:attributeValue("AXValue") ~= 1 then
      tab:performAction("AXPress")
      return
    end
    local desktop = checked("Desktop notifications")
    if desktop == nil then return end
    local mode = control(nil, "AXComboBox")
    return {
      desktop = desktop,
      threads = checked("Thread replies"),
      vips = checked("Messages from VIPs, even if notifications are paused"),
      mode = mode and mode:attributeValue("AXValue"),
    }
  end, function(values)
    if not alreadyOpen and app:isFrontmost() and control("Preferences", "AXHeading") then
      hs.eventtap.keyStroke({}, "escape", 0, app)
    end
    done(values)
  end)
end

local function readSlackStatus(done)
  local app = hs.application.get("com.tinyspeck.slackmacgap")
  local window = app and (app:mainWindow() or app:allWindows()[1])
  if not window then done(nil); return end
  local previous = hs.window.focusedWindow()
  local minimized, hidden = window:isMinimized(), app:isHidden()
  local openedMenu = false
  local function finish(value, preferences)
    local restoreFocus = app:isFrontmost()
    if minimized then window:minimize() end
    if hidden then app:hide() end
    if restoreFocus and previous and previous:id() ~= window:id() then previous:focus() end
    done(value, preferences)
  end
  local function read()
    if not app:isFrontmost() then return end
    local item, label = slackElement(hs.axuielement.applicationElement(app), function(title)
      return title == "Notifications On" or title == "Notifications Paused"
    end)
    if item then return label == "Notifications On" end
    if not openedMenu then
      local profile = slackElement(hs.axuielement.windowElement(window), function(title, role)
        return (role == "AXButton" or role == "AXPopUpButton") and title and title:match("^User: ")
      end)
      if profile then
        local frame = profile:attributeValue("AXFrame")
        if frame and frame.w > 0 and frame.h > 0 then
          hs.eventtap.leftClick({x = frame.x + frame.w / 2, y = frame.y + frame.h / 2})
          openedMenu = true
        end
      end
    end
  end
  if minimized then window:unminimize() end
  app:activate(true)
  window:focus()
  waitForSetting(read, function(value)
    if not app:isFrontmost() then finish(value); return end
    if openedMenu or value ~= nil then hs.eventtap.keyStroke({}, "escape", 0, app) end
    readSlackPreferences(app, function(preferences) finish(value, preferences) end)
  end, 4)
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
          readSlackStatus(function(inApp, preferences)
            states.slackInApp = inApp
            states.slackPreferences = preferences
            local swift = hs.task.new("/usr/bin/swift", function(code, output)
              local ok, audio = pcall(hs.json.decode, output)
              showConfiguration(value, code == 0 and ok and audio or nil, states, startup)
            end, {hs.configdir .. "/bin/audio_notification_status.swift"})
            if not swift or not swift:start() then showConfiguration(value, nil, states, startup) end
          end)
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
