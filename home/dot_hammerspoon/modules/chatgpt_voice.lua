-- Option+2 operates only the visible voice control in the current ChatGPT chat.

local function isChatGPT(app)
  if not app then return false end
  local id = app:bundleID()
  return id == "com.openai.chat" or
    (id == "com.openai.codex" and app:name() == "ChatGPT")
end


local function accessibleName(element)
  local names = {}
  for _, attribute in ipairs({ "AXDescription", "AXTitle", "AXValue", "AXHelp" }) do
    local value = element:attributeValue(attribute)
    if type(value) == "string" and value ~= "" then
      names[#names + 1] = value
    end
  end
  return table.concat(names, " ")
end

local function findAX(root, predicate)
  local visited, count = {}, 0
  local function walk(element, depth)
    if not element or visited[element] or depth > 45 or count >= 900 then return nil end
    visited[element] = true
    count = count + 1
    local role = element:attributeValue("AXRole")
    if predicate(element, role) then return element end
    local children = element:attributeValue("AXChildren")
    if type(children) == "table" then
      for _, child in ipairs(children) do
        local found = walk(child, depth + 1)
        if found then return found end
      end
    end
    return nil
  end
  return walk(root, 0)
end

local function currentAXRoot(app)
  local axApp = hs.axuielement.applicationElement(app)
  if axApp then axApp:setAttributeValue("AXManualAccessibility", true) end
  local window = app:focusedWindow() or app:mainWindow()
  if window then return hs.axuielement.windowElement(window) end
  return axApp
end


local function clickAXElement(element)
  local frame = element and element:attributeValue("AXFrame")
  local width = frame and (frame.w or frame.width)
  local height = frame and (frame.h or frame.height)
  if not (frame and width and height and width > 0 and height > 0) then
    return false
  end
  hs.eventtap.leftClick({ x = frame.x + width / 2, y = frame.y + height / 2 })
  return true
end

-- Option+2 only operates the existing chat's own voice control.
local voiceInFlight = false

local function existingChatVoiceButton(root)
  local function labelled(element, role, words)
    if role ~= "AXButton" then return false end
    local name = accessibleName(element):lower()
    if name:find("new voice chat", 1, true) then return false end
    return name:find(words, 1, true) ~= nil
  end

  -- Prefer ending an active session over starting anything.
  for _, label in ipairs({ "end voice chat", "cancel voice chat", "stop voice chat" }) do
    local button = findAX(root, function(element, role)
      return labelled(element, role, label)
    end)
    if button then return button, "stop" end
  end

  local button = findAX(root, function(element, role)
    return labelled(element, role, "start voice chat")
  end)
  if button then return button, "start" end
  return nil, nil
end

local function toggleCurrentChatVoice()
  if voiceInFlight then return end
  local app = hs.application.frontmostApplication()
  if not isChatGPT(app) then return end
  voiceInFlight = true

  HammerspoonConfig.afterModsReleased(function()
    voiceInFlight = false
    if hs.application.frontmostApplication() ~= app then return end
    local window = app:focusedWindow() or app:mainWindow()
    if not window then
      hs.alert.show("ChatGPT: no active chat window")
      return
    end

    local root = currentAXRoot(app)
    local button, action
    if root then button, action = existingChatVoiceButton(root) end
    if not button then
      hs.alert.show("ChatGPT: voice control not available in this chat")
      return
    end
    -- The app's empty/new-chat view is titled ChatGPT. Never start there.
    if action == "start" and (window:title() == "ChatGPT" or window:title() == "New chat") then
      hs.alert.show("ChatGPT: open an existing chat first")
      return
    end
    if button:attributeValue("AXEnabled") == false then
      hs.alert.show("ChatGPT: voice control is disabled")
      return
    end

    local originalMouse = hs.mouse.absolutePosition()
    if not clickAXElement(button) then
      hs.alert.show("ChatGPT: voice control has no accessible bounds")
      return
    end
    if originalMouse then
      hs.timer.doAfter(0.08, function() hs.mouse.absolutePosition(originalMouse) end)
    end
  end)
end

hs.hotkey.bind({ "alt" }, "2", toggleCurrentChatVoice)
