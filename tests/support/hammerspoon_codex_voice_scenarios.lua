-- Isolated Hammerspoon contract tests: no keyboard or app state is changed.
local module = assert(arg[1])
local scenario = assert(arg[2])

local events, alerts, queued = {}, {}, {}
local state = { warpRunning = scenario ~= "warp_missing" }

local warpApp, editorApp = {}, {}
local warpWindow, editorWindow = {}, {}
function warpApp:bundleID() return "dev.warp.Warp-Stable" end
function editorApp:bundleID() return "com.microsoft.VSCode" end
function editorApp:activate() state.frontApp, state.frontWindow = editorApp, editorWindow end
function warpApp:activate() state.frontApp, state.frontWindow = warpApp, warpWindow end
function warpWindow:id() return 88 end
function warpWindow:application() return warpApp end
function editorWindow:id() return 99 end
function editorWindow:application() return editorApp end
function warpWindow:isStandard() return scenario ~= "no_terminal" end
function warpWindow:focus()
  if scenario ~= "focus_blocked" then
    state.frontApp, state.frontWindow = warpApp, warpWindow
  end
end
function editorWindow:focus() state.frontApp, state.frontWindow = editorApp, editorWindow end
function warpApp:focusedWindow()
  if scenario == "no_terminal" then return nil end
  return warpWindow
end
function warpApp:mainWindow()
  if scenario == "no_terminal" then return nil end
  return warpWindow
end
function warpApp:allWindows()
  if scenario == "no_terminal" or scenario == "across_spaces" then return {} end
  return { warpWindow }
end
state.frontApp, state.frontWindow = editorApp, editorWindow
if scenario == "already_in_warp" then
  state.frontApp, state.frontWindow = warpApp, warpWindow
end

local hotkey, warpFocusObserver
HammerspoonConfig = { afterModsReleased = function(fn) state.deferred = fn end }
hs = {
  application = {
    get = function(bundle)
      assert(bundle == "dev.warp.Warp-Stable")
      return state.warpRunning and warpApp or nil
    end,
    frontmostApplication = function() return state.frontApp end,
  },
  window = {
    frontmostWindow = function() return state.frontWindow end,
    focusedWindow = function() return state.frontWindow end,
    get = function(id)
      -- An existing window on a different Mission Control Space is not
      -- returned by hs.window.get even though its handle can still focus it.
      if scenario == "across_spaces" then return nil end
      if id == 88 and scenario ~= "no_terminal" then return warpWindow end
      if id == 99 then return editorWindow end
      return nil
    end,
    filter = {
      windowFocused = "windowFocused",
      new = function()
        return { subscribe = function(_, event, callback)
          assert(event == "windowFocused")
          warpFocusObserver = callback
        end }
      end,
    },
  },
  hotkey = { bind = function(modifiers, key, callback)
    assert(#modifiers == 1 and modifiers[1] == "alt" and key == "1")
    hotkey = callback
  end },
  eventtap = { keyStroke = function(mods, key)
    assert(#mods == 0 and key:lower() == "f8")
    assert(state.frontApp == warpApp and state.frontWindow == warpWindow,
      "F8 must only reach the focused Warp window")
    table.insert(events, key)
  end },
  timer = { doAfter = function(_, fn) table.insert(queued, fn) end },
  alert = { show = function(message) table.insert(alerts, message) end },
}

dofile(module)
assert(type(hotkey) == "function")
if scenario == "across_spaces" then
  assert(type(warpFocusObserver) == "function")
  warpFocusObserver(warpWindow) -- Focused in Warp before switching to VS Code Space.
end
hotkey()
if scenario == "duplicate" then hotkey() end
if state.deferred then
  state.deferred()
else
  assert(scenario == "warp_missing" or scenario == "no_terminal",
    "A valid target must defer until Option is released")
end
for i = 1, 30 do
  if #queued == 0 then break end
  table.remove(queued, 1)()
end
assert(#queued == 0, "Timer queue did not drain")
if scenario == "warp_missing" or scenario == "no_terminal" or scenario == "focus_blocked" then
  assert(#events == 0, "Must never send F8 without a verified Warp target")
  assert(#alerts == 1, "Expected one actionable failure")
else
  assert(#events == 1, "Expected exactly one F8")
  assert(#alerts == 0, "Success should not show an alert")
end
if scenario == "already_in_warp" then
  assert(state.frontApp == warpApp and state.frontWindow == warpWindow)
else
  assert(state.frontApp == editorApp and state.frontWindow == editorWindow,
    "Original editor focus must be restored")
end
print("PASS " .. scenario)
