--------------------------------------------------------------------------- displays

local AD = AgentDesk
local HYPER = AD.hyper
local SEND_KEYS = { "j", "k", "l", ";" }
local FOCUS_KEYS = { "u", "i", "o", "p" }

LastWindowShortcut = "none"

-- Screens ordered left to right by their x position on the virtual desktop.
local function screensLeftToRight()
  local screens = hs.screen.allScreens()
  table.sort(screens, function(a, b)
    local fa, fb = a:fullFrame(), b:fullFrame()
    -- Stacked screens share an x; break the tie top-to-bottom so the
    -- numbering is stable (left to right, then top to bottom).
    if fa.x ~= fb.x then return fa.x < fb.x end
    return fa.y < fb.y
  end)
  return screens
end

local function screenAt(index)
  local target = screensLeftToRight()[index]
  if not target then
    hs.alert.show("No monitor " .. index)
  end
  return target
end

-- The screen the user is working on: where the focused window lives, falling
-- back to whichever screen macOS currently considers active.
local function currentScreen()
  local win = hs.window.focusedWindow()
  -- On an empty desktop there is no focused window; the mouse position says
  -- which monitor the user is actually working on, mainScreen often does not.
  return (win and win:screen()) or hs.mouse.screen() or hs.screen.mainScreen()
end

local function sendToScreen(index)
  local target = screenAt(index)
  if not target then return end

  -- Tahoe can expose zero-sized AXApplication placeholders instead of usable
  -- AXWindow objects. The standard Window menu remains reliable and moves the
  -- real focused window deterministically.
  local app = hs.application.frontmostApplication()
  local targetLabel = "Move to " .. target:name()
  if app and app:selectMenuItem({ "Window", targetLabel }) then
    hs.timer.doAfter(0.15, function()
      app:selectMenuItem({ "Window", "Fill" })
    end)
    return
  end

  -- macOS omits the menu item for the display the window is already on.
  if app then
    for _, screen in ipairs(screensLeftToRight()) do
      if screen ~= target
          and app:findMenuItem({ "Window", "Move to " .. screen:name() }) then
        app:selectMenuItem({ "Window", "Fill" })
        return
      end
    end
  end

  -- Fallback for apps which do not expose the standard Window menu.
  local win = hs.window.focusedWindow()
  if not win or not win:isStandard() then
    hs.alert.show("No movable focused window")
    return
  end

  -- A window in native macOS fullscreen owns its own Space and cannot be
  -- moved, so drop out of it first and let the animation settle.
  if win:isFullScreen() then
    win:setFullScreen(false)
    hs.timer.usleep(400000)
  end

  win:moveToScreen(target, false, true, 0)
  win:setFrame(target:frame())
  win:focus()
end

-- Focus the frontmost window living on `screen`. orderedWindows() is sorted
-- front to back, so the first match is the one that was most recently used
-- over there.
local function focusScreen(screen)
  for _, win in ipairs(hs.window.orderedWindows()) do
    if win:screen() == screen and win:isStandard() and win:isVisible() then
      win:focus()
      return true
    end
  end
  return false
end

-- With no window to focus, park the cursor on the screen instead: that is what
-- makes macOS treat it as the active display for the menu bar and for wherever
-- the next new window opens.
local function centerMouseOn(screen)
  local f = screen:frame()
  hs.mouse.absolutePosition({ x = f.x + f.w / 2, y = f.y + f.h / 2 })
end

local function focusScreenAt(index)
  local target = screenAt(index)
  if not target then return end

  if not focusScreen(target) then
    centerMouseOn(target)
    hs.alert.show("Monitor " .. index .. " (empty)", target)
  end
end

local function focusNextScreen()
  local current = currentScreen()
  local screens = screensLeftToRight()
  for i, screen in ipairs(screens) do
    if screen == current then
      focusScreenAt(i % #screens + 1)
      return
    end
  end
end

--------------------------------------------------------------------------- identify

-- Flash a card on every screen showing its number and the two keys bound to
-- it. Which physical monitor ends up as 1 depends on how things are cabled, so
-- this is the answer to "wait, which one is L again?" at a different desk.
local identifyCards = {}

local function clearIdentifyCards()
  for _, card in ipairs(identifyCards) do card:delete() end
  identifyCards = {}
end

local function identifyScreens()
  clearIdentifyCards()

  for i, screen in ipairs(screensLeftToRight()) do
    local full = screen:fullFrame()
    local w, h = 460, 320
    local card = hs.canvas.new({
      x = full.x + (full.w - w) / 2,
      y = full.y + (full.h - h) / 2,
      w = w,
      h = h,
    })

    card:appendElements(
      {
        type = "rectangle",
        action = "fill",
        roundedRectRadii = { xRadius = 32, yRadius = 32 },
        fillColor = { red = 0.05, green = 0.05, blue = 0.07, alpha = 0.88 },
      },
      {
        type = "text",
        text = tostring(i),
        textSize = 160,
        textColor = { white = 1 },
        textAlignment = "center",
        frame = { x = 0, y = 6, w = w, h = 190 },
      },
      {
        type = "text",
        text = "focus   ⌃⌥⌘ " .. (FOCUS_KEYS[i] or "-"):upper()
            .. "\nsend    ⌃⌥⌘ " .. (SEND_KEYS[i] or "-"):upper(),
        textSize = 26,
        textColor = { red = 0.55, green = 0.85, blue = 1, alpha = 1 },
        textAlignment = "center",
        frame = { x = 0, y = 196, w = w, h = 80 },
      },
      {
        type = "text",
        text = screen:name() or "",
        textSize = 15,
        textColor = { white = 0.6 },
        textAlignment = "center",
        frame = { x = 0, y = 282, w = w, h = 26 },
      }
    )

    card:level(hs.canvas.windowLevels.overlay)
    card:show(0.12)
    identifyCards[#identifyCards + 1] = card
  end

  hs.timer.doAfter(2.5, clearIdentifyCards)
end

-- Exposed for testing via the hs CLI.
Identify = identifyScreens

AD.screensLeftToRight = screensLeftToRight
AD.currentScreen = currentScreen
AD.focusScreen = focusScreen
AD.focusScreenAt = focusScreenAt

for i = 1, #SEND_KEYS do
  hs.hotkey.bind(HYPER, SEND_KEYS[i], function()
    LastWindowShortcut = "display:" .. i
    sendToScreen(i)
  end)
  hs.hotkey.bind(HYPER, FOCUS_KEYS[i], function() focusScreenAt(i) end)
  hs.hotkey.bind(HYPER, tostring(i), function() sendToScreen(i) end)
end

hs.hotkey.bind(HYPER, "n", focusNextScreen)
hs.hotkey.bind(HYPER, "h", identifyScreens)
