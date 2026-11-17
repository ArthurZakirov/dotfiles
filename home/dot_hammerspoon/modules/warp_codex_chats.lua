local warpBundle = "dev.warp.Warp-Stable"
local launcher = hs.configdir .. "/bin/warp-codex-chats"
local task
local managedWindow
local startupTimer

local function warp()
  return hs.application.get(warpBundle)
end

local function run(freshChat)
  if task then return end
  local app = warp()
  if not app then return end
  local previous = managedWindow
  local known = {}
  for _, window in ipairs(app:allWindows()) do known[window:id()] = true end
  local args = {launcher}
  if freshChat then args[2] = "--new" end
  local python = hs.fs.attributes("/opt/homebrew/bin/python3") and "/opt/homebrew/bin/python3"
    or "/usr/local/bin/python3"
  task = hs.task.new(python, function(code, stdout, stderr)
    task = nil
    if code ~= 0 then
      hs.printf("Warp Codex: %s", stderr)
      hs.alert.show("Warp: Codex-Start fehlgeschlagen")
      return
    end
    if freshChat or stdout:find("No eligible local Codex chats", 1, true) then return end
    local current = warp()
    if not current or current:pid() ~= app:pid() then return end
    local created = {}
    for _, window in ipairs(current:allWindows()) do
      if not known[window:id()] then table.insert(created, window) end
    end
    if #created ~= 1 then
      hs.alert.show("Warp: Codex-Fenster konnte nicht eindeutig erkannt werden")
      return
    end
    managedWindow = created[1]:id()
    local oldWindow = previous and hs.window.get(previous)
    local owner = oldWindow and oldWindow:application()
    if owner and owner:pid() == current:pid() then oldWindow:close() end
  end, args)
  if not task:start() then task = nil end
end

local newChat = hs.hotkey.new({"cmd"}, "t", function() run(true) end)
local refresh = hs.hotkey.new({"cmd"}, "r", function() run(false) end)
local function updateBindings(app)
  if app and app:bundleID() == warpBundle then
    newChat:enable()
    refresh:enable()
  else
    newChat:disable()
    refresh:disable()
  end
end

HammerspoonConfig.warpCodexWatcher = hs.application.watcher.new(function(_, event, app)
  if event == hs.application.watcher.activated then updateBindings(app) end
  if not app or app:bundleID() ~= warpBundle then return end
  if event == hs.application.watcher.launched then
    startupTimer = hs.timer.doAfter(2, function() run(false) end)
  elseif event == hs.application.watcher.terminated then
    managedWindow = nil
    if startupTimer then startupTimer:stop() end
    if task then task:terminate() end
  end
end):start()
updateBindings(hs.application.frontmostApplication())
HammerspoonConfig.refreshWarpCodex = function() run(false) end
