-- Exercise the public audio shortcut with fake Hammerspoon host APIs.
-- Only the OS-owned boundaries (audio devices, timers, tasks, canvas) are faked.
local config_dir, scenario, mute, expected_label = ...
table.unpack = table.unpack or unpack -- LuaJIT implements Lua 5.1.
HammerspoonConfig = { hyper = { "ctrl", "alt", "cmd" } }
local timers, tasks, cards = {}, {}, {}
local bindings = {}
local mute_value = ({ muted = true, unmuted = false })[mute]
local output = {
  name = function() return "Arctis Nova 7 Gen 2" end,
  uid = function() return "output-1" end,
  outputVolume = function() return 40 end,
  outputMuted = function() return mute_value end,
}
local input = {
  name = function() return "Arctis Nova 7 Gen 2" end,
  inputVolume = function() return 40 end,
  inputMuted = function() return mute_value end,
}
local function timer(delay, fn)
  local t = { delay = delay, fn = fn, stopped = false }
  function t:stop() self.stopped = true end
  timers[#timers + 1] = t
  return t
end
local function fire(t)
  -- Host callbacks can already be queued when cancellation occurs.
  t.fn()
end
local function latestTimer(delay)
  for i = #timers, 1, -1 do
    if timers[i].delay == delay then return timers[i] end
  end
  error("No timer with delay " .. delay)
end
local screen = { frame = function() return { x = 0, y = 0, w = 1600, h = 900 } end }
hs = {
  configdir = config_dir,
  hotkey = { bind = function(_, key, fn) bindings[key] = fn end },
  mouse = { getCurrentScreen = function() return screen end },
  screen = { mainScreen = function() return screen end },
  audiodevice = {
    defaultOutputDevice = function() return output end,
    defaultInputDevice = function() return input end,
    allOutputDevices = function() return { output } end,
  },
  sound = { getByFile = function() return nil end },
  timer = { doAfter = timer },
  styledtext = { new = function(text) return text end },
  canvas = {
    windowLevels = { overlay = 1 },
    new = function()
      local card = { deleted = false, elements = {} }
      function card:appendElements(...) self.elements = {...} end
      function card:level() return self end
      function card:show() return self end
      function card:delete() self.deleted = true end
      setmetatable(card, {
        __index = function(self, index)
          if type(index) == "number" then return self.elements[index] end
        end,
      })
      cards[#cards + 1] = card
      return card
    end,
  },
  task = {
    new = function(path, completed, streamed)
      assert(path == config_dir .. "/bin/mic_level")
      local t = { completed = completed, streamed = streamed, running = false }
      function t:start() self.running = true; return true end
      function t:isRunning() return self.running end
      function t:terminate() self.running = false end
      tasks[#tasks + 1] = t
      return t
    end,
  },
}
dofile(config_dir .. "/modules/audio_check.lua")
assert(type(bindings["ä"]) == "function", "Audio shortcut was not registered")
local press = bindings["ä"]
local function valueAt(card, y)
  for _, element in ipairs(card.elements) do
    if element.type == "text" and element.frame.y == y and element.frame.x == 245 then
      return element
    end
  end
end
if scenario == "mute" then
  press()
  local row = assert(valueAt(cards[1], 212), "No output mute row")
  assert(row.text == expected_label, "Expected " .. expected_label .. ", got " .. tostring(row.text))
  local input_row = assert(valueAt(cards[1], 390), "No input mute row")
  local expected_input = mute == "unknown" and "Wird durch Mikrofontest geprüft" or expected_label
  assert(input_row.text == expected_input,
    "Expected input " .. expected_input .. ", got " .. tostring(input_row.text))
  -- Check which channel dominates, not mere presence of RGB keys: all
  -- three status colors have all three numeric (truthy) channels.
  local expected_channel = ({ unknown = "blue", unmuted = "green", muted = "red" })[mute]
  for _, status_row in ipairs({ row, input_row }) do
    local color = status_row.textColor
    for _, channel in ipairs({ "red", "green", "blue" }) do
      if channel ~= expected_channel then
        assert(color[expected_channel] > color[channel],
          "Expected " .. expected_channel .. " status to dominate " .. channel)
      end
    end
  end
elseif scenario == "restart_pending" then
  press()
  local stale = latestTimer(0.8)
  press()
  local current = cards[#cards]
  assert(cards[1].deleted)
  assert(stale.stopped, "Previous scheduled start must be cancelled")
  fire(stale)
  assert(#tasks == 0, "Old callback must not start microphone check")
  fire(latestTimer(0.8))
  assert(#tasks == 1, "Latest run must start one task")
  assert(not current.deleted, "Latest results must still be visible")
elseif scenario == "restart_active" then
  press()
  fire(latestTimer(0.8))
  local stale = tasks[#tasks]
  press()
  local current = cards[#cards]
  assert(not current.deleted)
  fire(latestTimer(0.8))
  local active = tasks[#tasks]
  assert(active ~= stale)
  local before = #timers
  stale.completed(1, "", "old task failed")
  stale.streamed(nil, "0.0000\n", "")
  assert(#timers == before, "Old completion must not schedule a close")
  assert(not current.deleted, "Old completion must not delete current results")
  assert(active.streamed(nil, "0.0030\n", "") == false)
  assert(valueAt(current, 426).text == "Signal erkannt")
  assert(valueAt(current, 390).text == "Nicht stumm – Signal erkannt")
elseif scenario == "no_signal" then
  press()
  fire(latestTimer(0.8))
  tasks[#tasks].completed(0, "", "")
  assert(valueAt(cards[1], 426).text == "Kein Signal erkannt")
else
  error("Unknown test scenario " .. tostring(scenario))
end
