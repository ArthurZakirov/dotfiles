-- Exercise the real PR navigation module against disposable Hammerspoon APIs.
local config_root, scenario = arg[1], arg[2]
local url = "https://github.com/ArthurZakirov/dotfiles/pull/48"
if scenario == "github_branch" then
  url = "https://github.com/ArthurZakirov/dotfiles/tree/main"
elseif scenario == "bitbucket_pr" then
  url = "https://bitbucket.org/team/app/pull-requests/12"
end

local running = scenario ~= "chrome_stopped"
local focused = scenario == "chrome_focused"
local captured = { alerts = {} }
HammerspoonConfig = {
  hyper = { "ctrl", "alt", "cmd" },
  afterModsReleased = function(callback) captured.afterRelease = callback end,
}
hs = {
  application = {
    get = function(bundle)
      assert(bundle == "com.google.Chrome")
      return running and {} or nil
    end,
    frontmostApplication = function()
      return { bundleID = function()
        return focused and "com.google.Chrome" or "com.openai.chatgpt"
      end }
    end,
  },
  alert = { show = function(message)
    table.insert(captured.alerts, message)
  end },
  osascript = { applescript = function(script)
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
assert(captured.helper == nil, "must wait for modifier release")
captured.afterRelease()

if scenario == "chrome_stopped" or scenario == "chrome_unreadable" then
  assert(captured.helper == nil, "should not run without a readable Chrome tab")
  assert(#captured.alerts == 1)
else
  assert(#captured.alerts == 0)
  assert(captured.helper:match("/%.local/bin/git%-pr$"))
  assert(captured.arguments[1] == "open-local")
  assert(captured.arguments[2] == url)
  assert(captured.environment.PATH:find("/opt/homebrew/bin", 1, true))
end
