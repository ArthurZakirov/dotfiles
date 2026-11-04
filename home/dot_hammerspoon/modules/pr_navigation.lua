-- Chrome GitHub/Bitbucket PR or branch -> linked VS Code worktree.
local runningTask

local function chromeWebAppUrl(app)
  -- Chrome-installed web apps run as separate bundles (com.google.Chrome.app.*).
  -- Unlike Chrome tabs, their document URLs are exposed through Accessibility
  -- as an NSURL table on an AXGroup/AXWebArea.
  local ok, url = pcall(function()
    local element = hs.axuielement.applicationElement(app)
    if not element then return nil end
    local windows = element:attributeValue("AXWindows")
    local window = element:attributeValue("AXFocusedWindow")
      or (type(windows) == "table" and windows[1])
    if not window then return nil end

    local visited = 0
    local function documentUrl(node, depth)
      visited = visited + 1
      if depth > 6 or visited > 120 then return nil end
      local role = node:attributeValue("AXRole")
      if role == "AXGroup" or role == "AXWebArea" then
        local value = node:attributeValue("AXURL")
        local candidate = type(value) == "table" and value.url or value
        if type(candidate) == "string" and candidate:match("^https?://") then
          return candidate
        end
      end
      local children = node:attributeValue("AXChildren")
      if type(children) == "table" then
        for _, child in ipairs(children) do
          local found = documentUrl(child, depth + 1)
          if found then return found end
        end
      end
      return nil
    end

    return documentUrl(window, 0)
  end)
  return ok and url or nil
end

local function openLocalBranch(sourceApp)
  if runningTask then
    hs.alert.show("A worktree navigation request is still running")
    return
  end

  local bundleID = sourceApp and sourceApp:bundleID() or ""
  local url
  if bundleID:match("^com%.google%.Chrome%.app%.") then
    url = chromeWebAppUrl(sourceApp)
    if not url then
      hs.alert.show("Cannot read Chrome web app URL. Check Hammerspoon Accessibility permission.")
      return
    end
  else
    if not hs.application.get("com.google.Chrome") then
      hs.alert.show("Open a GitHub or Bitbucket PR/branch in Chrome first")
      return
    end
    local ok, tabUrl = hs.osascript.applescript([[
      tell application "Google Chrome"
        if (count windows) = 0 then return ""
        return URL of active tab of front window
      end tell
    ]])
    if not ok or type(tabUrl) ~= "string" or tabUrl == "" then
      hs.alert.show("Cannot read Chrome tab. Check Hammerspoon Automation permission.")
      return
    end
    url = tabUrl
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
  -- Capture the web-app identity before waiting for modifier-key release:
  -- focus can change before afterModsReleased invokes the callback.
  local sourceApp = hs.application.frontmostApplication()
  HammerspoonConfig.afterModsReleased(function()
    openLocalBranch(sourceApp)
  end)
end)
