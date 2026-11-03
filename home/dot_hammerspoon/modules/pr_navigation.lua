-- Chrome GitHub/Bitbucket PR or branch -> linked VS Code worktree.
local runningTask

local function openLocalBranch()
  local front = hs.application.frontmostApplication()
  if not front or front:bundleID() ~= "com.google.Chrome" then
    hs.alert.show("Open a GitHub or Bitbucket PR/branch in Chrome first")
    return
  end
  if runningTask then
    hs.alert.show("A worktree navigation request is still running")
    return
  end

  local ok, url = hs.osascript.applescript([[
    tell application "Google Chrome"
      if (count windows) = 0 then return ""
      return URL of active tab of front window
    end tell
  ]])
  if not ok or type(url) ~= "string" or url == "" then
    hs.alert.show("Cannot read Chrome tab. Check Hammerspoon Automation permission.")
    return
  end

  local helper = os.getenv("HOME") .. "/.local/bin/git-pr"
  runningTask = hs.task.new(helper, function(exitCode, stdout, stderr)
    runningTask = nil
    if exitCode ~= 0 then
      hs.alert.show(stderr ~= "" and stderr or "Could not open branch worktree", 6)
    end
  end, { "open-local", url })
  if runningTask then
    local environment = runningTask:environment()
    environment.PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" .. (environment.PATH or "")
    runningTask:setEnvironment(environment)
    if runningTask:start() then return end
  end
  runningTask = nil
  hs.alert.show("Cannot start ~/.local/bin/git-pr")
end

-- The Python Bitbucket Chrome lookup uses this chooser when several open PRs
-- match the same source branch. Keep the interface consumed by that helper.
HammerspoonConfig.chooseBitbucketPullRequest = function(choices)
  local chooser = hs.chooser.new(function(choice)
    HammerspoonConfig.bitbucketPrChooser = nil
    if choice then hs.urlevent.openURLWithBundle(choice.url, "com.google.Chrome") end
  end)
  HammerspoonConfig.bitbucketPrChooser = chooser
  chooser:placeholder("Choose the pull request to open")
  chooser:choices(choices)
  chooser:show()
  return true
end

hs.hotkey.bind(HammerspoonConfig.hyper, "v", function()
  HammerspoonConfig.afterModsReleased(openLocalBranch)
end)
