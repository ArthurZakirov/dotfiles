-- Rectangle-compatible placement keys. Prefer Tahoe's native Window menu;
-- Rectangle remains a fallback for apps without those standard menu items.
local function rectangleAction(action)
  hs.execute('/usr/bin/open -g "rectangle://execute-action?name=' .. action .. '"', true)
end

local function nativeWindowAction(path, fallback)
  local app = hs.application.frontmostApplication()
  if not app or not app:selectMenuItem(path) then rectangleAction(fallback) end
end

hs.hotkey.bind({ "ctrl", "alt" }, "left", function()
  LastWindowShortcut = "left-half"
  nativeWindowAction({ "Window", "Move & Resize", "Left" }, "left-half")
end)

hs.hotkey.bind({ "ctrl", "alt" }, "right", function()
  LastWindowShortcut = "right-half"
  nativeWindowAction({ "Window", "Move & Resize", "Right" }, "right-half")
end)

hs.hotkey.bind({ "ctrl", "alt" }, "return", function()
  LastWindowShortcut = "maximize"
  nativeWindowAction({ "Window", "Fill" }, "maximize")
end)
