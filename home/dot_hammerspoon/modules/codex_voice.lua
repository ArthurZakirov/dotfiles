-- Deliver F8 to the selected terminal, then restore the original application.
local config = hs.json.read(os.getenv("HOME") .. "/.config/codex-voice/config.json") or {}
local terminal = config.terminal_app or "Herdr"
local bundles = { Herdr = "dev.herdr.app", Warp = "dev.warp.Warp-Stable" }
local bundle = bundles[terminal]
if not bundle then
  hs.alert.show("Codex terminal_app must be Herdr or Warp")
  return
end
local lastWindow
local inFlight = false

local function isTerminalWindow(win)
  if not win or not win:id() then return false end
  local app = win:application()
  -- A remembered window may be on another Space; hs.window.get(id)
  -- only searches the current one, so the stored handle is authoritative.
  return app and app:bundleID() == bundle and win:isStandard()
end

-- Remember the user's intended Warp window, not an arbitrary terminal window.
local terminalFilter = hs.window.filter.new(terminal)
terminalFilter:subscribe(hs.window.filter.windowFocused, function(win)
  if isTerminalWindow(win) then lastWindow = win end
end)

local function targetWindow()
  local app = hs.application.get(bundle)
  if not app then return nil, terminal .. " is not running" end

  local focused = hs.window.focusedWindow()
  if isTerminalWindow(focused) then return focused end
  if isTerminalWindow(lastWindow) then return lastWindow end

  -- On a fresh Hammerspoon start, one Warp window is unambiguous.
  local windows = {}
  for _, win in ipairs(app:allWindows()) do
    if isTerminalWindow(win) and win:isStandard() then
      windows[#windows + 1] = win
    end
  end
  if #windows == 1 then return windows[1] end
  if #windows == 0 then return nil, "No " .. terminal .. " terminal window found" end
  return nil, "Focus the intended " .. terminal .. " window once, then retry"
end

local function toggleVoice()
  if inFlight then return end

  local target, problem = targetWindow()
  if not target then hs.alert.show(problem) return end

  inFlight = true
  local originalApp = hs.application.frontmostApplication()
  local originalWindow = hs.window.focusedWindow()

  local function restoreFocus()
    local restored = false
    if originalWindow and originalWindow:id() then
      -- The original window may now be on another Space too.
      local ok, focused = pcall(function() return originalWindow:focus() end)
      restored = ok and focused ~= nil and focused ~= false
    end
    if not restored and originalApp then originalApp:activate() end
    inFlight = false
  end

  HammerspoonConfig.afterModsReleased(function()
    -- Wait for actual Warp focus before synthesizing F8. Otherwise the
    -- keystroke could leak into VS Code or another foreground application.
    local attempts = 0
    local function deliverWhenFocused()
      local activeApp = hs.application.frontmostApplication()
      local activeWindow = hs.window.focusedWindow()
      if activeApp and activeApp:bundleID() == bundle
        and activeWindow and activeWindow:id() == target:id() then
        hs.eventtap.keyStroke({}, "f8", 20)
        hs.timer.doAfter(0.15, restoreFocus)
        return
      end
      attempts = attempts + 1
      if attempts >= 20 then
        restoreFocus()
        hs.alert.show(terminal .. " did not receive focus; voice unchanged")
      else
        hs.timer.doAfter(0.05, deliverWhenFocused)
      end
    end

    target:focus()
    hs.timer.doAfter(0.05, deliverWhenFocused)
  end)
end

hs.hotkey.bind({ "alt" }, "1", toggleVoice)
