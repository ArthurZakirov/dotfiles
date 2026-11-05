-- A dedicated, keyboard-toggleable Kanban window; no Chrome tabs.
local URL = "http://127.0.0.1:6420"
local board

local function toggleBoard()
  if board and board:isVisible() then
    board:hide()
    return
  end

  if not board then
    local screen = hs.screen.mainScreen():frame()
    local width = math.floor(screen.w * 0.86)
    local height = math.floor(screen.h * 0.86)
    local rect = {
      x = screen.x + math.floor((screen.w - width) / 2),
      y = screen.y + math.floor((screen.h - height) / 2),
      w = width,
      h = height,
    }
    board = hs.webview.new(rect)
      :url(URL)
      :windowTitle("Agent Backlog")
      :deleteOnClose(false)
  end

  board:show()
  board:bringToFront(true)
end

HammerspoonConfig.agentBacklog = {
  toggle = toggleBoard,
  isVisible = function() return board ~= nil and board:isVisible() end,
}

hs.hotkey.bind({ "alt" }, "k", toggleBoard)
