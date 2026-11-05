-- Global Option+1 controls F8 in the most recently focused Warp window.
-- Warp is focused only for delivery, then the original application is restored.
-- No tmux, Codex fork, or background terminal session is required.

local WARP_BUNDLE = "dev.warp.Warp-Stable"
local lastWarpWindow
local inFlight = false

local function isWarpWindow(win)
  if not win or not win:id() then return false end
  local app = win:application()
  return app and app:bundleID() == WARP_BUNDLE and win:isStandard()
    and hs.window.get(win:id()) ~= nil
end

-- Remember the user's intended Warp window, not an arbitrary terminal window.
local warpFilter = hs.window.filter.new("Warp")
warpFilter:subscribe(hs.window.filter.windowFocused, function(win)
  if isWarpWindow(win) then lastWarpWindow = win end
end)

local function targetWarpWindow()
  local app = hs.application.get(WARP_BUNDLE)
  if not app then return nil, "Warp is not running" end

  local focused = hs.window.focusedWindow()
  if isWarpWindow(focused) then return focused end
  if isWarpWindow(lastWarpWindow) then return lastWarpWindow end

  -- On a fresh Hammerspoon start, one Warp window is unambiguous.
  local windows = {}
  for _, win in ipairs(app:allWindows()) do
    if isWarpWindow(win) and win:isStandard() then
      windows[#windows + 1] = win
    end
  end
  if #windows == 1 then return windows[1] end
  if #windows == 0 then return nil, "No Warp terminal window found" end
  return nil, "Focus the intended Warp window once, then retry"
end

local function toggleVoice()
  if inFlight then return end

  local target, problem = targetWarpWindow()
  if not target then hs.alert.show(problem) return end

  inFlight = true
  local originalApp = hs.application.frontmostApplication()
  local originalWindow = hs.window.focusedWindow()

  local function restoreFocus()
    if originalWindow and originalWindow:id()
      and hs.window.get(originalWindow:id()) then
      originalWindow:focus()
    elseif originalApp then
      originalApp:activate()
    end
    inFlight = false
  end

  HammerspoonConfig.afterModsReleased(function()
    -- Wait for actual Warp focus before synthesizing F8. Otherwise the
    -- keystroke could leak into VS Code or another foreground application.
    local attempts = 0
    local function deliverWhenFocused()
      local activeApp = hs.application.frontmostApplication()
      local activeWindow = hs.window.focusedWindow()
      if activeApp and activeApp:bundleID() == WARP_BUNDLE
        and activeWindow and activeWindow:id() == target:id() then
        hs.eventtap.keyStroke({}, "f8", 20)
        hs.timer.doAfter(0.15, restoreFocus)
        return
      end
      attempts = attempts + 1
      if attempts >= 20 then
        restoreFocus()
        hs.alert.show("Warp did not receive focus; voice unchanged")
      else
        hs.timer.doAfter(0.05, deliverWhenFocused)
      end
    end

    target:focus()
    hs.timer.doAfter(0.05, deliverWhenFocused)
  end)
end

hs.hotkey.bind({ "alt" }, "1", toggleVoice)
