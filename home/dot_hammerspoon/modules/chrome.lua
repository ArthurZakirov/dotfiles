--------------------------------------------------------------- chrome omnibox scopes

local HYPER = AgentDesk.hyper
local afterModsReleased = AgentDesk.afterModsReleased

-- Focus Chrome and open the omnibox pre-scoped (@bookmarks / @tabs / @history:
-- typing the scope then Tab activates Chrome's scoped search). The synthetic
-- cmd+L must not fire while the HYPER modifiers are still held, and Chrome
-- needs a beat to become frontmost before it receives the keystrokes.
local function chromeScopedSearch(scope)
  afterModsReleased(function()
    hs.application.launchOrFocus("Google Chrome")
    hs.timer.doAfter(0.2, function()
      hs.eventtap.keyStroke({ "cmd" }, "l", 0)
      hs.eventtap.keyStrokes(scope)
      hs.timer.doAfter(0.05, function()
        hs.eventtap.keyStroke({}, "tab", 0)
      end)
    end)
  end)
end

hs.hotkey.bind(HYPER, "b", function() chromeScopedSearch("@bookmarks") end)
hs.hotkey.bind(HYPER, "t", function() chromeScopedSearch("@tabs") end)
hs.hotkey.bind(HYPER, "g", function() chromeScopedSearch("@history") end)
