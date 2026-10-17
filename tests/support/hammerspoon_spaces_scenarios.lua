-- Invoke the public window-to-Space shortcut against a simulated macOS host.
local config_dir, scenario = ...
HammerspoonConfig = {
  hyper = { "ctrl", "alt", "cmd" },
  currentScreen = function() end,
  focusScreen = function() end,
  screensLeftToRight = function() return {} end,
  afterModsReleased = function(fn) fn() end,
}
local bindings, timers = {}, {}
local events = { down = 0, up = 0, key = 0, restore = 0, focus = 0 }
local screen = { getUUID = function() return "display-1" end }
local window = {
  isStandard = function() return true end,
  isFullScreen = function() return false end,
  screen = function() return screen end,
  zoomButtonRect = function() return {} end,
  focus = function() events.focus = events.focus + 1 end,
}
local mouse = { x = 12, y = 34 }
local function after(delay, fn)
  local timer = { delay = delay, callback = fn, stopped = false }
  function timer:stop() self.stopped = true end
  timers[#timers + 1] = timer
  return timer
end
local function fire(delay)
  for i = #timers, 1, -1 do
    if timers[i].delay == delay then
      timers[i].callback()
      return
    end
  end
  error("Timer " .. delay .. " missing")
end
local poller
hs = {
  hotkey = {
    bind = function(_, key, fn) bindings[key] = fn end,
    modal = { new = function()
      return { bind = function() end, enter = function() end, exit = function() end }
    end },
  },
  window = { focusedWindow = function() return window end },
  spaces = {
    spacesForScreen = function() return { 10, 20 } end,
    spaceType = function() return "user" end,
    activeSpaceOnScreen = function() return 20 end,
    windowSpaces = function() return { 20 } end,
  },
  alert = { show = function(message) error("Unexpected alert: " .. message) end },
  mouse = {
    absolutePosition = function(pos)
      if pos then
        events.restore = events.restore + 1
        mouse = pos
      else
        return mouse
      end
    end,
  },
  geometry = function()
    return { move = function()
      return { topleft = { x = 40, y = 50 } }
    end }
  end,
  eventtap = {
    event = {
      types = { leftMouseUp = 1, leftMouseDown = 2 },
      newMouseEvent = function(kind)
        return { post = function()
          if kind == 1 then events.up = events.up + 1 end
          if kind == 2 then events.down = events.down + 1 end
        end }
      end,
    },
    keyStroke = function() events.key = events.key + 1 end,
  },
  timer = {
    doAfter = after,
    waitUntil = function(_, callback)
      poller = { stopped = false, complete = callback }
      function poller:stop() self.stopped = true end
      return poller
    end,
  },
}
dofile(config_dir .. "/modules/spaces.lua")
assert(type(bindings["m"]) == "function")
bindings["m"]() -- Window-to-previous-Space is the public entry point.
assert(events.down == 1, "Window must be grabbed")
fire(0.15)
assert(events.key == 1, "Space move shortcut must be triggered")
assert(poller, "Window move must be monitored")
if scenario == "move_failed" then
  fire(2) -- No Space change; fallback releases the grabbed mouse.
elseif scenario == "move_succeeded" then
  poller.complete()
  fire(2) -- A later fallback must not repeat the release.
else
  error("Unknown scenario " .. tostring(scenario))
end
assert(events.down == 1 and events.up == 1, "Grab must be released exactly once")
assert(events.restore == 1, "Original cursor position must be restored")
assert(events.focus == 1, "Focused window must be restored")
assert(poller.stopped, "Completed or failed move must stop polling")
