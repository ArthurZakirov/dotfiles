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
  AgentDesk.afterModsReleased(function()
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

local function update()
  if isChatGPT(hs.application.frontmostApplication()) and germanLayout() then
    shortcut:enable()
  else
    shortcut:disable()
  end
end

-- Retain watchers and the hotkey across garbage collection.
AgentDesk.chatgpt = {
  shortcut = shortcut,
  watcher = hs.application.watcher.new(function(_, event)
    if event == hs.application.watcher.activated or
      event == hs.application.watcher.deactivated or
      event == hs.application.watcher.terminated then update() end
  end),
}
AgentDesk.chatgpt.watcher:start()
hs.keycodes.inputSourceChanged(update)
update()
