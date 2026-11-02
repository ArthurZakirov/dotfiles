-- Read-only freshness check for the *visible* Codex desktop conversation.
-- The native Copy chat deep link command supplies its exact session ID.
local M = {}

local PIPELINE = hs.configdir .. "/bin/agents_md_pipeline"
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
  M.lastResult = nil
  runNumber = runNumber + 1
  if pollTimer then pollTimer:stop(); pollTimer = nil end
  if closeTimer then closeTimer:stop(); closeTimer = nil end
  if checkerTask and checkerTask:isRunning() then checkerTask:terminate() end
  checkerTask = nil
  if card then card:delete(); card = nil end
  return runNumber
end

local STAGE_LABELS = {
  "GitHub main",
  "Lokales main",
  "Guidance erzeugt",
  "Chezmoi apply",
  "Codex-Kontext",
}

local function unknownResult(reason)
  local stages = {}
  for index, label in ipairs(STAGE_LABELS) do
    stages[index] = { label = label, status = "unknown", detail = reason }
  end
  return { overall = "unknown", stages = stages }
end

local function show(result)
  M.lastResult = result
  if card then card:delete(); card = nil end
  local stages = result.stages or {}
  local current = 0
  for _, stage in ipairs(stages) do
    if stage.status == "current" then current = current + 1 end
  end
  local headline = "AGENTS.md · " .. current .. "/" .. #STAGE_LABELS .. " aktuell"
  local width, height = 670, 344
  local screen = hs.mouse.getCurrentScreen() or hs.screen.mainScreen()
  local frame = screen:frame()
  card = hs.canvas.new({
    x = frame.x + (frame.w - width) / 2,
    y = frame.y + (frame.h - height) / 2,
    w = width, h = height,
  })
  local elements = {
    {
      type = "rectangle", action = "fill",
      roundedRectRadii = { xRadius = 22, yRadius = 22 },
      fillColor = { red = 0.045, green = 0.047, blue = 0.06, alpha = 0.97 },
    },
    {
      type = "text", text = headline, textColor = COLORS.white,
      textFont = ".AppleSystemUIFontBold", textSize = 23,
      frame = { x = 28, y = 20, w = width - 56, h = 37 },
    },
  }
  for i, label in ipairs(STAGE_LABELS) do
    local stage = stages[i] or { status = "unknown", detail = "Nicht geprüft" }
    local status = stage.status
    local symbol = status == "current" and "✓" or status == "outdated" and "✕" or "?"
    local color = status == "current" and COLORS.green
      or status == "outdated" and COLORS.red or COLORS.blue
    local y = 78 + (i - 1) * 49
    elements[#elements + 1] = {
      type = "text", text = symbol, textColor = color,
      textFont = ".AppleSystemUIFontBold", textSize = 24,
      frame = { x = 29, y = y - 3, w = 38, h = 36 },
    }
    elements[#elements + 1] = {
      type = "text", text = label, textColor = COLORS.white,
      textSize = 17, frame = { x = 70, y = y, w = 214, h = 28 },
    }
    elements[#elements + 1] = {
      type = "text", text = tostring(stage.detail or ""), textColor = color,
      textSize = 14, frame = { x = 291, y = y + 1, w = 348, h = 27 },
    }
  end
  card:appendElements((table.unpack or unpack)(elements))
  card:level(hs.canvas.windowLevels.overlay)
  card:show(0.10)
  if closeTimer then closeTimer:stop(); closeTimer = nil end
  local duration = result.overall == "current" and 3 or 4
  closeTimer = hs.timer.doAfter(duration, function()
    if card then card:delete(); card = nil end
    closeTimer = nil
  end)
end

local function check(sessionId, run)
  if not hs.fs.attributes(PIPELINE, "mode") then
    show(unknownResult("Pipeline-Checker fehlt"))
    return
  end
  if not hs.fs.attributes(PYTHON, "mode") then
    show(unknownResult("Python nicht verfügbar"))
    return
  end
  local args = { PIPELINE }
  if sessionId then
    args[#args + 1] = "--session-id"
    args[#args + 1] = sessionId
  end
  local task = hs.task.new(PYTHON, function(code, stdout, stderr)
    if run ~= runNumber then return end
    checkerTask = nil
    if code ~= 0 then
      show(unknownResult("Pipeline-Fehler " .. tostring(code)))
      return
    end
    local ok, result = pcall(hs.json.decode, stdout)
    if not ok or type(result) ~= "table" or type(result.stages) ~= "table"
      or #result.stages ~= #STAGE_LABELS then
      show(unknownResult("Ungültiges Pipeline-Ergebnis"))
      return
    end
    show(result)
  end, args)
  if not task or not task:start() then
    show(unknownResult("Pipeline konnte nicht starten"))
    return
  end
  checkerTask = task
end

local function captureSession(app, run)
  -- readAllData/writeAllData retain rich formats of the first clipboard item.
  -- Multi-item clipboard contents cannot safely be round-tripped here.
  local items = hs.pasteboard.allContentTypes()
  if items and #items > 1 then
    check(nil, run)
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
        check(nil, run)
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
      check(nil, run)
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
    show(unknownResult("Codex Desktop öffnen"))
    return
  end
  captureSession(app, run)
end

-- Explicit ID entry point for deterministic diagnostics without app automation.
function M.checkSession(sessionId)
  check(sessionId, stopPrevious())
end

hs.hotkey.bind(HammerspoonConfig.hyper, HOTKEY, M.run)
HammerspoonConfig.agentsFreshness = M
return M
