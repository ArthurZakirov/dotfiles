-- Exercise the production Chrome/Chrome-Web-App navigation callback with fake macOS APIs.
local config_root, scenario = arg[1], arg[2]
local pwa = scenario:match("^pwa_") ~= nil
local url = "https://github.com/ArthurZakirov/dotfiles/pull/48/changes"
if scenario == "github_branch" then
  url = "https://github.com/ArthurZakirov/dotfiles/tree/main"
elseif scenario == "bitbucket_pr" or scenario == "pwa_bitbucket_pr" then
  url = "https://bitbucket.org/team/app/pull-requests/12"
elseif scenario == "bitbucket_comment" or scenario == "pwa_bitbucket_comment" then
  url = "https://bitbucket.org/team/app/pull-requests/12#comment-8192"
end

local running = scenario ~= "chrome_stopped"
local pwaBundle = "com.google.Chrome.app.mjoklplbddabcmpepnokjaffbmgbkkgg"
local captured = { alerts = {}, focusChanged = false }
local sourceApp = {
  bundleID = function()
    if pwa then return pwaBundle end
    return scenario == "chrome_focused" and "com.google.Chrome" or "com.openai.chatgpt"
  end,
}
local otherApp = { bundleID = function() return "com.openai.chatgpt" end }

local document = {
  attributeValue = function(_, key)
    if key == "AXRole" then return "AXGroup" end
    if key == "AXURL" then
      if scenario == "pwa_unreadable" then return nil end
      if scenario == "pwa_string_url" then return url end
      return { __luaSkinType = "NSURL", url = url }
    end
    if key == "AXChildren" then return {} end
  end,
}
local inner = {
  attributeValue = function(_, key)
    if key == "AXRole" then return "AXGroup" end
    if key == "AXChildren" then return { document } end
  end,
}
local window = {
  attributeValue = function(_, key)
    if key == "AXRole" then return "AXWindow" end
    if key == "AXChildren" then
      return { scenario == "pwa_nested_group" and inner or document }
    end
  end,
}
local axApp = {
  attributeValue = function(_, key)
    if key == "AXFocusedWindow" and scenario ~= "pwa_windows_fallback" then
      return window
    end
    if key == "AXWindows" then return { window } end
  end,
}

HammerspoonConfig = {
  hyper = { "ctrl", "alt", "cmd" },
  afterModsReleased = function(callback) captured.afterRelease = callback end,
}
hs = {
  application = {
    get = function(bundle)
      assert(not pwa, "A Chrome web app must not require a regular Chrome window")
      assert(bundle == "com.google.Chrome")
      return running and {} or nil
    end,
    frontmostApplication = function()
      if captured.focusChanged then return otherApp end
      return sourceApp
    end,
  },
  axuielement = {
    applicationElement = function(app)
      assert(pwa, "Regular Chrome must not use the web-app Accessibility reader")
      assert(app == sourceApp, "Must read from the app that owned the shortcut")
      if scenario == "pwa_ax_error" then error("Accessibility denied") end
      return axApp
    end,
  },
  alert = { show = function(message)
    table.insert(captured.alerts, message)
  end },
  osascript = { applescript = function(script)
    assert(not pwa, "Web-app URL must not be read from a regular Chrome tab")
    assert(script:find("active tab of front window", 1, true))
    if scenario == "chrome_unreadable" then return false, nil end
    return true, url
  end },
  task = { new = function(helper, callback, arguments)
    return {
      environment = function() return { PATH = "/usr/bin" } end,
      setEnvironment = function(_, env) captured.environment = env end,
      start = function()
        captured.helper = helper
        captured.arguments = arguments
        return true
      end,
    }
  end },
  hotkey = { bind = function(modifiers, key, callback)
    assert(key == "v")
    captured.hotkey = callback
  end },
  chooser = { new = function() return {} end },
  urlevent = { openURLWithBundle = function() end },
}

dofile(config_root .. "/modules/pr_navigation.lua")
assert(type(captured.hotkey) == "function")
captured.hotkey()
assert(captured.helper == nil, "Must wait for modifier release")
captured.focusChanged = scenario == "pwa_focus_changed"
captured.afterRelease()

local blocked = scenario == "chrome_stopped"
  or scenario == "chrome_unreadable"
  or scenario == "pwa_unreadable"
  or scenario == "pwa_ax_error"

if blocked then
  assert(captured.helper == nil, "Must not run without a readable URL")
  assert(#captured.alerts == 1)
  if pwa then
    assert(captured.alerts[1]:find("web app URL", 1, true))
  end
else
  assert(#captured.alerts == 0)
  assert(captured.helper:match("/%.local/bin/git%-pr$"))
  assert(captured.arguments[1] == "open-local")
  assert(captured.arguments[2] == url)
  assert(captured.environment.PATH:find("/opt/homebrew/bin", 1, true))
end
