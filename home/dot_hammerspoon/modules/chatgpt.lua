-- German slash is Shift+7, while ChatGPT's menu accelerator is Cmd+/.
-- Invoke the native command instead of synthesising a layout-dependent key.
local function isChatGPT(app)
  if not app then return false end
  local id = app:bundleID()
  return id == "com.openai.chat" or
    (id == "com.openai.codex" and app:name() == "ChatGPT")
end

local function germanLayout()
  local source = hs.keycodes.currentSourceID() or ""
  return source:find("QWERTZ", 1, true) ~= nil or
    source:find("German", 1, true) ~= nil
end

local shortcut = hs.hotkey.new({ "cmd", "shift" }, 26, function()
  local target = hs.application.frontmostApplication()
  HammerspoonConfig.afterModsReleased(function()
    -- Do not act on a different app if focus changes while keys are held.
    if not isChatGPT(target) or
      hs.application.frontmostApplication() ~= target then return end
    for _, title in ipairs({ "Keyboard Shortcuts", "Tastaturkürzel" }) do
      if target:findMenuItem(title) then
        if target:selectMenuItem(title) then return end
      end
    end
    hs.alert.show("ChatGPT: keyboard shortcuts menu not found")
  end)
end)

-- ChatGPT 26.1027 exposes its ChatGPT/Codex switcher as an AXPopUpButton.
-- Its menu items are AXMenuItems. Resolve both by accessible names instead of
-- relying on screen locations or Ctrl+1/2/3 (those navigate recent chats).
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

local function modeButton(root)
  return findAX(root, function(element, role)
    return role == "AXPopUpButton" and
      accessibleName(element):find("Switch mode, current mode:", 1, true) ~= nil
  end)
end

local function modeName(button)
  local name = accessibleName(button)
  if name:find("current mode: ChatGPT", 1, true) then return "ChatGPT" end
  if name:find("current mode: Codex", 1, true) then return "Codex" end
  return nil
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

local function toggleChatGPTCodex()
  local app = hs.application.frontmostApplication()
  if not isChatGPT(app) then return end

  HammerspoonConfig.afterModsReleased(function()
    if hs.application.frontmostApplication() ~= app then return end

    local root = currentAXRoot(app)
    local button = root and modeButton(root)
    local from = button and modeName(button)
    if not from then
      hs.alert.show("ChatGPT: mode switcher not found")
      return
    end

    local destination = from == "ChatGPT" and "Codex" or "ChatGPT"
    local originalMouse = hs.mouse.absolutePosition()
    -- AXPress is not reliable on this application's custom switcher.
    -- Click the live accessible bounds, never a stored pixel coordinate.
    if not clickAXElement(button) then
      hs.alert.show("ChatGPT: mode switcher has no accessible bounds")
      return
    end

    local function selectDestination(attempt)
      if hs.application.frontmostApplication() ~= app then return end
      -- Popup menus are separate AX windows: neither the ChatGPT window
      -- nor AXApplication AXChildren contains their menu items.
      -- Hit-test below the live switcher bounds, but act ONLY on an
      -- AXMenuItem whose accessible label matches the required destination.
      local switcherFrame = button:attributeValue("AXFrame")
      local item
      if switcherFrame then
        local sw = hs.axuielement.systemWideElement()
        local x = switcherFrame.x + switcherFrame.w / 2
        for offset = 12, 175, 12 do
          local hit = sw:elementAtPosition({
            x = x, y = switcherFrame.y + switcherFrame.h + offset,
          })
          if hit and hit:attributeValue("AXRole") == "AXMenuItem" then
            local label = accessibleName(hit)
            if label == destination or label:find(destination .. " ", 1, true) then
              item = hit
              break
            end
          end
        end
      end

      if not item then
        if attempt < 8 then
          hs.timer.doAfter(0.09, function() selectDestination(attempt + 1) end)
        else
          hs.alert.show("ChatGPT: " .. destination .. " menu item not found")
        end
        return
      end

      -- The current app exposes AXMenuItem but rejects programmatic AXPress.
      -- A synthetic click at *this element's live AXFrame* works; no fixed
      -- coordinates or mouse-dependent positioning are stored in the config.
      if not clickAXElement(item) then
        hs.alert.show("ChatGPT: mode menu has no accessible bounds")
        return
      end
      -- Restore the original pointer after the mode menu closes.
      if originalMouse then
        hs.timer.doAfter(0.08, function() hs.mouse.absolutePosition(originalMouse) end)
      end

      hs.timer.doAfter(1.0, function()
        if not isChatGPT(app) then return end
        local nextRoot = currentAXRoot(app)
        local nextButton = nextRoot and modeButton(nextRoot)
        if not nextButton or modeName(nextButton) ~= destination then
          hs.alert.show("ChatGPT: could not verify switch to " .. destination)
        end
      end)
    end
    hs.timer.doAfter(0.12, function() selectDestination(1) end)
  end)
end

local modeToggle = hs.hotkey.new(HammerspoonConfig.hyper, "c", toggleChatGPTCodex)

local function update()
  local onChatGPT = isChatGPT(hs.application.frontmostApplication())
  if onChatGPT then modeToggle:enable() else modeToggle:disable() end
  if onChatGPT and germanLayout() then
    shortcut:enable()
  else
    shortcut:disable()
  end
end

-- Retain watchers and both hotkeys across garbage collection.
HammerspoonConfig.chatgpt = {
  shortcut = shortcut,
  modeToggle = modeToggle,
  toggleMode = toggleChatGPTCodex,
  watcher = hs.application.watcher.new(function(_, event)
    if event == hs.application.watcher.activated or
      event == hs.application.watcher.deactivated or
      event == hs.application.watcher.terminated then update() end
  end),
}
HammerspoonConfig.chatgpt.watcher:start()
hs.keycodes.inputSourceChanged(update)
update()
