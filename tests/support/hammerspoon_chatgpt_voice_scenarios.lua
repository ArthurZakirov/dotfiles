-- Isolated Option+2 behaviour tests; do not control the actual desktop.
local module, scenario = assert(arg[1]), assert(arg[2])
local alerts, clicks, queued = {}, {}, {}
local cursor = { x = 100, y = 200 }

local function element(role, label, frame, enabled, children)
  local attrs = {
    AXRole = role, AXDescription = label, AXFrame = frame,
    AXEnabled = enabled, AXChildren = children or {},
  }
  return { attributeValue = function(_, key) return attrs[key] end }
end

local frame = { x = 400, y = 300, w = 30, h = 34 }
local controls = {}
if scenario == "start" or scenario == "empty_chat" or
  scenario == "disabled" or scenario == "no_bounds" or
  scenario == "focus_changed" or scenario == "double" then
  local buttonFrame = scenario == "no_bounds" and {} or frame
  controls = { element("AXButton", "Start voice chat",
    buttonFrame, scenario ~= "disabled") }
elseif scenario == "end" then
  controls = { element("AXButton", "End voice chat", frame, true) }
elseif scenario == "cancel" then
  controls = { element("AXButton", "Cancel voice chat", frame, true) }
elseif scenario == "prefer_end" then
  controls = {
    element("AXButton", "Start voice chat", frame, true),
    element("AXButton", "End voice chat", {x = 520, y = 300, w = 30, h = 34}, true),
  }
elseif scenario == "new_voice" then
  controls = { element("AXButton", "Start new voice chat", frame, true) }
elseif scenario == "dictation" then
  controls = { element("AXButton", "Dictate", frame, true) }
else
  assert(scenario == "wrong_app")
end
local axRoot = element("AXWindow", "chat", nil, true, controls)
local app = {}
local otherApp = {}
function otherApp:bundleID() return "com.apple.finder" end
function otherApp:name() return "Finder" end
local window = {}
function app:bundleID() return "com.openai.codex" end
function app:name() return "ChatGPT" end
function app:focusedWindow() return window end
function app:mainWindow() return window end
function window:title()
  if scenario == "empty_chat" or scenario == "end" then return "ChatGPT" end
  return "Existing conversation"
end

local frontApp = scenario == "wrong_app" and otherApp or app
local voiceHotkey, deferred
HammerspoonConfig = {
  hyper = { "ctrl", "alt", "cmd" },
  afterModsReleased = function(fn) deferred = fn end,
}
local function toggleable() return {enable = function() end, disable = function() end} end
hs = {
  hotkey = {
    new = function() return toggleable() end,
    bind = function(mods, key, fn)
      assert(#mods == 1 and mods[1] == "alt" and key == "2")
      voiceHotkey = fn
    end,
  },
  application = {
    frontmostApplication = function() return frontApp end,
    watcher = {
      activated = 1, deactivated = 2, terminated = 3,
      new = function() return { start = function() end } end,
    },
  },
  keycodes = {
    currentSourceID = function() return "German" end,
    inputSourceChanged = function() end,
  },
  axuielement = {
    applicationElement = function()
      return { setAttributeValue = function() end }
    end,
    windowElement = function() return axRoot end,
  },
  eventtap = {
    leftClick = function(point) clicks[#clicks + 1] = point end,
  },
  mouse = {
    absolutePosition = function(point)
      if point then cursor = point end
      return cursor
    end,
  },
  timer = { doAfter = function(_, fn) queued[#queued + 1] = fn end },
  alert = { show = function(message) alerts[#alerts + 1] = message end },
}

dofile(module)
assert(type(voiceHotkey) == "function", "Option+2 must be registered")
voiceHotkey()
if scenario == "double" then voiceHotkey() end
if scenario == "focus_changed" then frontApp = otherApp end
if deferred then deferred() end
while #queued > 0 do
  table.remove(queued, 1)()
end

local expectedClick = ({
  start = true, ["end"] = true, cancel = true,
  prefer_end = true, double = true,
})[scenario]
assert(#clicks == (expectedClick and 1 or 0),
  "Unexpected button click count: " .. #clicks .. " for " .. scenario)
if scenario == "prefer_end" then
  assert(clicks[1].x == 535, "Active voice must take priority over starting voice")
end
local expectAlert = ({
  empty_chat = true, disabled = true, no_bounds = true,
  new_voice = true, dictation = true,
})[scenario]
assert(#alerts == (expectAlert and 1 or 0),
  "Unexpected alert count: " .. #alerts .. " for " .. scenario)
assert(cursor.x == 100 and cursor.y == 200, "Mouse position must be restored")
print("PASS " .. scenario)
