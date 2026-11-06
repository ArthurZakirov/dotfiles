-- Capture the exact visible Codex desktop thread using its native Copy Link shortcut.
-- Shared by AGENTS.md freshness and desktop-to-terminal resume.
local M = {}
local captureInProgress = false
local APP_IDS = { ["com.openai.codex"] = true, ["com.openai.chatgpt"] = true }

function M.isDesktopApp(app)
  return app and APP_IDS[app:bundleID()] == true
end

function M.capture(app, callback)
  if captureInProgress then
    callback(nil, "Codex session capture already in progress")
    return function() end
  end
  if not M.isDesktopApp(app) then
    callback(nil, "Codex Desktop is not frontmost")
    return function() end
  end

  -- We cannot safely round-trip a clipboard containing multiple items.
  local items = hs.pasteboard.allContentTypes()
  if items and #items > 1 then
    callback(nil, "Clipboard has multiple items")
    return function() end
  end

  captureInProgress = true
  local original = hs.pasteboard.readAllData()
  local changeCount = hs.pasteboard.changeCount()
  local timer
  local active = true
  local attempts = 0

  local function finish(sessionId, problem)
    if not active then return end
    active = false
    captureInProgress = false
    if timer then timer:stop(); timer = nil end
    callback(sessionId, problem)
  end

  -- This changes the clipboard, not the chat composer.
  hs.eventtap.keyStroke({ "cmd", "alt" }, "l", 0, app)

  local function poll()
    if not active then return end
    attempts = attempts + 1
    local now = hs.pasteboard.changeCount()
    if now ~= changeCount then
      local contents = hs.pasteboard.getContents() or ""
      local sid = contents:match("^codex://threads/([0-9a-fA-F%-]+)$")
      local chunks = {}
      if sid then
        for chunk in sid:gmatch("[0-9a-fA-F]+") do
          chunks[#chunks + 1] = chunk
        end
      end
      if sid and sid:match("^[0-9a-fA-F%-]+$")
        and #chunks == 5
        and #chunks[1] == 8 and #chunks[2] == 4 and #chunks[3] == 4
        and #chunks[4] == 4 and #chunks[5] == 12
        and #sid == 36 then
        -- Only restore if no other process changed the clipboard meanwhile.
        if hs.pasteboard.changeCount() == now then
          if original and next(original) then
            hs.pasteboard.writeAllData(original)
          else
            hs.pasteboard.clearContents()
          end
        end
        finish(sid:lower())
      else
        -- Unknown clipboard writes are potentially user-owned. Never clobber.
        finish(nil, "Native shortcut did not return a Codex thread link")
      end
      return
    end
    if attempts >= 15 then
      finish(nil, "Native Copy Link did not update the clipboard")
      return
    end
    timer = hs.timer.doAfter(0.1, poll)
  end

  timer = hs.timer.doAfter(0.1, poll)
  return function()
    if not active then return end
    active = false
    captureInProgress = false
    if timer then timer:stop(); timer = nil end
  end
end

return M
