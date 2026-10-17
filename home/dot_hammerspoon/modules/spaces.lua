local AD = AgentDesk
local HYPER = AD.hyper
local currentScreen = AD.currentScreen
local focusScreen = AD.focusScreen
local screensLeftToRight = AD.screensLeftToRight
local afterModsReleased = AD.afterModsReleased

local function spacesOn(screen, userOnly)
  local ids = hs.spaces.spacesForScreen(screen:getUUID()) or {}
  if not userOnly then return ids end
  local user = {}
  for _, id in ipairs(ids) do
    if hs.spaces.spaceType(id) == "user" then user[#user + 1] = id end
  end
  return user
end

local function indexOf(list, value)
  for i, item in ipairs(list) do
    if item == value then return i end
  end
end

-- Step one space left or right on the current screen. Synthetic ctrl+arrow
-- keystrokes are ignored by this macOS, so drive Mission Control through
-- hs.spaces.gotoSpace instead.
local function switchSpace(delta)
  local screen = currentScreen()
  local ids = spacesOn(screen, false)
  local here = indexOf(ids, hs.spaces.activeSpaceOnScreen(screen:getUUID()))
  local target = here and ids[here + delta]
  if not target then
    hs.alert.show(delta < 0 and "No space to the left" or "No space to the right")
    return
  end
  hs.spaces.gotoSpace(target)
  -- Land with the keyboard already pointed at something on the new space.
  hs.timer.doAfter(0.4, function() focusScreen(screen) end)
end

-- Move the focused window one space left or right and follow it. The private
-- API for this (hs.spaces.moveWindowToSpace) silently does nothing on this
-- macOS, so replay the human gesture: hold the window by its title bar with a
-- synthetic mouse press, then hit the native move-space shortcut -- the held
-- window rides along with the switch. (ctrl+fn+arrow: the fn flag is what real
-- arrow-key presses carry, without it the shortcut is ignored.)
local function moveWindowSpace(delta)
  local win = hs.window.focusedWindow()
  if not win or not win:isStandard() then
    hs.alert.show("No focused window")
    return
  end
  if win:isFullScreen() then
    hs.alert.show("Cannot move a fullscreen window")
    return
  end

  local screen = win:screen()
  local ids = spacesOn(screen, true)
  local here = indexOf(ids, hs.spaces.activeSpaceOnScreen(screen:getUUID()))
  local target = here and ids[here + delta]
  if not target then
    hs.alert.show(delta < 0 and "No space to the left" or "No space to the right")
    return
  end

  afterModsReleased(function()
    local et = hs.eventtap.event
    local initial = hs.spaces.windowSpaces(win)
    initial = initial and initial[1]
    -- Just next to the zoom button: always on the title bar, never on a control.
    local grab = hs.geometry(win:zoomButtonRect()):move({ -1, -1 }).topleft
    local restore = hs.mouse.absolutePosition()
    local released = false
    local function release()
      if released then return end
      released = true
      et.newMouseEvent(et.types.leftMouseUp, grab):post()
      hs.mouse.absolutePosition(restore)
      win:focus()
    end

    et.newMouseEvent(et.types.leftMouseDown, grab):post()
    hs.timer.doAfter(0.15, function()
      hs.eventtap.keyStroke({ "ctrl", "fn" }, delta < 0 and "left" or "right", 0)
      hs.timer.waitUntil(
        function()
          local ws = hs.spaces.windowSpaces(win)
          return ws and ws[1] and ws[1] ~= initial
        end,
        release,
        0.05
      )
      -- Never leave the mouse button stuck down if the move fails.
      hs.timer.doAfter(2, release)
    end)
  end)
end

-- Exposed for testing via the hs CLI.
MoveTest = moveWindowSpace

-- Keyboard window picker: a Spotlight-style searchable list of every open
-- window on every monitor and space. Type part of a title or app name, Enter
-- to jump there, Escape to close.
local function createSpace()
  local screen = currentScreen()
  local ok, err = hs.spaces.addSpaceToScreen(screen:getUUID(), true)
  if not ok then
    hs.alert.show("Could not create space: " .. tostring(err), screen)
    return
  end
  -- Give Mission Control a moment to register the new space before jumping.
  hs.timer.doAfter(0.6, function()
    local ids = spacesOn(screen, true)
    hs.spaces.gotoSpace(ids[#ids])
    hs.alert.show("Space " .. #ids .. " created", screen)
  end)
end

-- Interactive space manager: ctrl+alt+cmd+backspace shows, on every monitor,
-- a card listing its desktops (macOS numbering, active mark, window count).
-- Press a desktop's number to delete exactly that desktop -- no need to
-- navigate to it first; deleting the active one hops to a neighbor. Escape or
-- Return closes.
local spaceCards = {}
local spaceIndex = {} -- desktop number -> { id = spaceID, screen = hs.screen }
local delMode = hs.hotkey.modal.new()

local function clearSpaceCards()
  for _, card in ipairs(spaceCards) do card:delete() end
  spaceCards = {}
end

-- Count real windows per space, walking every app's windows (the only way
-- that sees windows on other spaces).
local function windowCountsBySpace()
  local counts = {}
  for _, app in ipairs(hs.application.runningApplications()) do
    if app:kind() == 1 then
      for _, w in ipairs(app:allWindows()) do
        if w:isStandard() then
          local ws = hs.spaces.windowSpaces(w)
          if ws and ws[1] then counts[ws[1]] = (counts[ws[1]] or 0) + 1 end
        end
      end
    end
  end
  return counts
end

local function showSpaceCards()
  clearSpaceCards()
  spaceIndex = {}
  local names = hs.spaces.missionControlSpaceNames()
  local counts = windowCountsBySpace()

  for _, screen in ipairs(screensLeftToRight()) do
    local u = screen:getUUID()
    local active = hs.spaces.activeSpaceOnScreen(u)
    local lines = {}
    for _, id in ipairs(spacesOn(screen, true)) do
      local label = (names[u] and names[u][id]) or ("Space " .. id)
      local n = tonumber(tostring(label):match("(%d+)$"))
      if n then spaceIndex[n] = { id = id, screen = screen } end
      local c = counts[id] or 0
      lines[#lines + 1] = string.format("%s%s   %s",
        label, id == active and "  \u{25CF}" or "",
        c == 0 and "empty" or (c .. (c == 1 and " window" or " windows")))
    end

    local f = screen:fullFrame()
    local w, h = 460, 90 + #lines * 34
    local card = hs.canvas.new({ x = f.x + (f.w - w) / 2, y = f.y + (f.h - h) / 2, w = w, h = h })
    card:appendElements(
      { type = "rectangle", action = "fill",
        roundedRectRadii = { xRadius = 24, yRadius = 24 },
        fillColor = { red = 0.05, green = 0.05, blue = 0.07, alpha = 0.92 } },
      { type = "text", text = "Delete which desktop?",
        textSize = 22, textColor = { white = 1 }, textAlignment = "center",
        frame = { x = 0, y = 18, w = w, h = 32 } },
      { type = "text", text = table.concat(lines, "\n"),
        textSize = 19, textColor = { red = 0.55, green = 0.85, blue = 1 },
        textAlignment = "center",
        frame = { x = 0, y = 60, w = w, h = #lines * 34 } },
      { type = "text", text = "number = delete \u{00B7} esc = close",
        textSize = 13, textColor = { white = 0.55 }, textAlignment = "center",
        frame = { x = 0, y = h - 26, w = w, h = 20 } }
    )
    card:level(hs.canvas.windowLevels.overlay)
    card:show(0.1)
    spaceCards[#spaceCards + 1] = card
  end
end

local function deleteDesktop(n)
  local entry = spaceIndex[n]
  if not entry then
    hs.alert.show("No desktop " .. n)
    return
  end
  local screen, sid = entry.screen, entry.id
  local ids = spacesOn(screen, true)
  if #ids < 2 then
    hs.alert.show("Last space on that monitor", screen)
    return
  end

  local function removeAndRefresh()
    local ok, err = hs.spaces.removeSpace(sid)
    if not ok then
      hs.alert.show("Could not delete: " .. tostring(err), screen)
    end
    hs.timer.doAfter(0.6, showSpaceCards)
  end

  local active = hs.spaces.activeSpaceOnScreen(screen:getUUID())
  if sid == active then
    local here = indexOf(ids, sid)
    hs.spaces.gotoSpace(ids[here - 1] or ids[here + 1])
    hs.timer.doAfter(0.9, removeAndRefresh)
  else
    removeAndRefresh()
  end
end

function delMode:entered() showSpaceCards() end
function delMode:exited() clearSpaceCards() end

for n = 1, 9 do
  delMode:bind({}, tostring(n), function() deleteDesktop(n) end)
end
delMode:bind({}, "escape", function() delMode:exit() end)
delMode:bind({}, "return", function() delMode:exit() end)
delMode:bind(HYPER, "delete", function() delMode:exit() end)

hs.hotkey.bind(HYPER, "+", createSpace)
hs.hotkey.bind(HYPER, "delete", function() delMode:enter() end)
hs.hotkey.bind(HYPER, ",", function() switchSpace(-1) end)
hs.hotkey.bind(HYPER, ".", function() switchSpace(1) end)
hs.hotkey.bind(HYPER, "m", function() moveWindowSpace(-1) end)
hs.hotkey.bind(HYPER, "-", function() moveWindowSpace(1) end)
hs.hotkey.bind(HYPER, "space", hs.spaces.toggleMissionControl)
hs.hotkey.bind(HYPER, "z", function()
  local win = hs.window.focusedWindow()
  if not win then
    hs.alert.show("No window to expose")
    return
  end
  win:focus()
  hs.spaces.toggleAppExpose()
end)
