-- Managed Hammerspoon entrypoint.
-- Each concern owns its own bindings and implementation under modules/.

hs.window.animationDuration = 0
require("hs.ipc")

HammerspoonConfig = {
  hyper = { "ctrl", "alt", "cmd" },
}

dofile(hs.configdir .. "/modules/core.lua")
dofile(hs.configdir .. "/modules/displays.lua")
dofile(hs.configdir .. "/modules/spaces.lua")
dofile(hs.configdir .. "/modules/window_picker.lua")
dofile(hs.configdir .. "/modules/chrome.lua")
dofile(hs.configdir .. "/modules/claude.lua")
dofile(hs.configdir .. "/modules/chatgpt.lua")
dofile(hs.configdir .. "/modules/layout.lua")

hs.hotkey.bind(HammerspoonConfig.hyper, "r", hs.reload)
hs.autoLaunch(true)
dofile(hs.configdir .. "/modules/audio_check.lua")

hs.alert.show("Hammerspoon config loaded")

-- Published only after every module has loaded and baseline hotkeys are active.
-- An activation nonce distinguishes this load from a previous running instance.
local activeHotkeys = #hs.hotkey.getHotkeys()
if activeHotkeys < 28 then
  error("Hammerspoon: expected at least 28 active base hotkeys, got " .. activeHotkeys)
end
HammerspoonConfig.readyNonce = hs.settings.get("dotfiles.activation_nonce") or ""
