-- Read-only freshness check for the *visible* Codex desktop conversation.
-- The native Copy chat deep link command supplies its exact session ID.
local M = {}

local CHECKER = os.getenv("HOME") .. "/.codex/hooks-json/agents-md-freshness/check.py"
local PYTHON = "/opt/homebrew/bin/python3"
local APP_IDS = { ["com.openai.codex"] = true, ["com.openai.chatgpt"] = true }
local HOTKEY = "f" -- ctrl + alt + cmd + f, separate from audio-test shortcut.

local card
local closeTimer
local pollTimer
local checkerTask
local runNumber = 0
local COLORS = {
  white = { white = 0.95 },
  muted = { white = 0.65 },
  green = { red = 0.34, green = 0.86, blue = 0.48 },
  red = { red = 1, green = 0.35, blue = 0.35 },
  blue = { red = 0.48, green = 0.76, blue = 1 },
}

local function stopPrevious()
  runNumber = runNumber + 1
  if pollTimer then pollTimer:stop(); pollTimer = nil end
  if closeTimer then closeTimer:stop(); closeTimer = nil end
  if checkerTask and checkerTask:isRunning() then checkerTask:terminate() end
  checkerTask = nil
  if card then card:delete(); card = nil end
  return runNumber
end

local function show(status, detail, version)
  M.lastResult = { status = status, detail = detail, version = version }
  if card then card:delete(); card = nil end
  local color, symbol, headline, duration
  if status == "current" then
    color, symbol, headline, duration = COLORS.green, "✅", "AGENTS.md current", 1.4
  elseif status == "outdated" then
    color, symbol, headline, duration = COLORS.red, "❌", "AGENTS.md outdated", 2
  else
    color, symbol, headline, duration = COLORS.blue, "❔", "AGENTS.md not verified", 2
  end
  local screen = hs.mouse.getCurrentScreen() or hs.screen.mainScreen()
  local frame = screen:frame()
  local width, height = 510, 173
  card = hs.canvas.new({
    x = frame.x + (frame.w - width) / 2,
    y = frame.y + (frame.h - height) / 2,
    w = width, h = height,
  })
  card:appendElements(
    {
      type = "rectangle", action = "fill",
      roundedRectRadii = { xRadius = 22, yRadius = 22 },
      fillColor = { red = 0.045, green = 0.047, blue = 0.06, alpha = 0.97 },
    },
    {
      type = "text", text = symbol,
      frame = { x = 25, y = 19, w = 42, h = 42 }, textSize = 28,
    },
    {
      type = "text", text = headline, textColor = color,
      textFont = ".AppleSystemUIFontBold", textSize = 23,
      frame = { x = 75, y = 24, w = 410, h = 34 },
    },
    {
      type = "text", text = detail or "", textColor = COLORS.white,
      textSize = 16, frame = { x = 27, y = 79, w = 455, h = 34 },
    },
    {
      type = "text", text = version or "Read-only · no agent interaction",
      textColor = COLORS.muted, textSize = 13,
      frame = { x = 27, y = 127, w = 455, h = 22 },
    }
  )
  card:level(hs.canvas.windowLevels.overlay)
  card:show(0.10)
  if closeTimer then closeTimer:stop(); closeTimer = nil end
  if duration then
    closeTimer = hs.timer.doAfter(duration, function()
      if card then card:delete(); card = nil end
      closeTimer = nil
    end)
  end
end

local function showResult(result, sessionId)
  local status = result and result.status or "unknown"
  if status == "current" or status == "outdated" then
    local from = result.seen_source_digest or (result.seen_sha256 or ""):sub(1, 12)
    local to = result.current_source_digest or (result.current_sha256 or ""):sub(1, 12)
    show(status, "Session " .. sessionId:sub(1, 8),
      "Loaded " .. from .. "  ·  Disk " .. to)
  else
    show("unknown", (result and result.reason) or "Checker returned no usable result")
  end
end

local function check(sessionId, run)
  if not hs.fs.attributes(CHECKER, "mode") then
    show("unknown", "The local freshness checker is not installed")
    return
  end
  if not hs.fs.attributes(PYTHON, "mode") then
    show("unknown", "Homebrew Python is unavailable")
    return
  end
  local task = hs.task.new(PYTHON, function(code, stdout, stderr)
    if run ~= runNumber then return end
    checkerTask = nil
    if code ~= 0 then
      show("unknown", "Checker failed: " .. (stderr or ""):sub(1, 85))
      return
    end
    local ok, result = pcall(hs.json.decode, stdout)
    if not ok or type(result) ~= "table" or result.session_id ~= sessionId then
      show("unknown", "Checker returned no matching session result")
      return
    end
    showResult(result, sessionId)
  end, { CHECKER, "--check", "--session-id", sessionId })
  if not task or not task:start() then
    show("unknown", "Unable to start the local checker")
    return
  end
  checkerTask = task
end

local function captureSession(app, run)
  -- readAllData/writeAllData retain rich formats of the first clipboard item.
  -- Multi-item clipboard contents cannot safely be round-tripped here.
  local items = hs.pasteboard.allContentTypes()
  if items and #items > 1 then
    show("unknown", "Clipboard has multiple items; not modifying it")
    return
  end
  local original = hs.pasteboard.readAllData()
  local originalCount = hs.pasteboard.changeCount()
  local tries = 0
  -- Native desktop action. Never types into or submits the composer.
  hs.eventtap.keyStroke({ "cmd", "alt" }, "l", 0, app)

  local function poll()
    if run ~= runNumber then return end
    tries = tries + 1
    local now = hs.pasteboard.changeCount()
    if now ~= originalCount then
      local contents = hs.pasteboard.getContents() or ""
      local sid = contents:match("^codex://threads/([0-9a-fA-F]+%-[0-9a-fA-F]+%-[0-9a-fA-F]+%-[0-9a-fA-F]+%-[0-9a-fA-F]+)$")
      if not sid or #sid ~= 36 then
        show("unknown", "Desktop app did not copy a local Codex chat link")
        return
      end
      -- Only restore when nobody else has changed the clipboard since the copy.
      if hs.pasteboard.changeCount() == now then
        if original and next(original) then
          hs.pasteboard.writeAllData(original)
        else
          hs.pasteboard.clearContents()
        end
      end
      check(sid, run)
      return
    end
    if tries >= 15 then
      show("unknown", "Desktop app did not supply a chat deep link")
      return
    end
    pollTimer = hs.timer.doAfter(0.1, poll)
  end
  pollTimer = hs.timer.doAfter(0.1, poll)
end

function M.run()
  local run = stopPrevious()
  local app = hs.application.frontmostApplication()
  if not app or not APP_IDS[app:bundleID()] then
    show("unknown", "Open a ChatGPT / Codex desktop chat first")
    return
  end
  captureSession(app, run)
end

hs.hotkey.bind(HammerspoonConfig.hyper, HOTKEY, M.run)
HammerspoonConfig.agentsFreshness = M
return M
