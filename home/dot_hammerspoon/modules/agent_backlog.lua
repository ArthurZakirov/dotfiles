-- A dedicated, keyboard-toggleable Kanban window; no Chrome tabs.
local URL = "http://127.0.0.1:6420"
local PREFERRED_MONITOR = "DELL U3225QE"
local board

local function targetScreen()
  return hs.screen.find(PREFERRED_MONITOR) or hs.screen.mainScreen()
end

local function centeredFrame(screen)
  local available = screen:frame()
  local width = math.floor(available.w * 0.86)
  local height = math.floor(available.h * 0.86)
  return {
    x = available.x + math.floor((available.w - width) / 2),
    y = available.y + math.floor((available.h - height) / 2),
    w = width,
    h = height,
  }
end

local function focusSearch()
  if not board or not board:isVisible() then return end
  -- Backlog.md supports Cmd-K in browsers, but macOS may consume that key
  -- equivalent before a Hammerspoon-hosted WKWebView sees the event.
  board:evaluateJavaScript([[
    (() => {
      const input = document.querySelector('input[placeholder^="Search ("]');
      if (!input) return false;
      input.focus();
      input.select();
      return true;
    })()
  ]])
end

-- This shortcut must never replace Cmd-K in other applications.
local searchHotkey = hs.hotkey.new({ "cmd" }, "k", focusSearch)

local function toggleBoard()
  if board and board:isVisible() then
    board:hide()
    searchHotkey:disable()
    return
  end

  local screen = targetScreen()
  local rect = centeredFrame(screen)

  if not board then
    board = hs.webview.new(rect)
      :url(URL)
      :allowTextEntry(true)
      :windowTitle("Agent Backlog")
      :deleteOnClose(false)
      :windowCallback(function(action, _, focused)
        if action == "focusChange" then
          if focused then searchHotkey:enable() else searchHotkey:disable() end
        end
      end)
  end

  -- A previously hidden WebView retains its old coordinates. Reposition on
  -- every open, even after display rearrangement or a macOS window relocation.
  board:show()
  board:frame(rect)
  local window = board:hswindow()
  if window then
    window:moveToScreen(screen, false, true, 0)
    window:setFrame(rect)
    window:focus()
  end
  board:bringToFront()
end

HammerspoonConfig.agentBacklog = {
  toggle = toggleBoard,
  isVisible = function() return board ~= nil and board:isVisible() end,
  screenName = function()
    local window = board and board:hswindow()
    local screen = window and window:screen()
    return screen and screen:name() or nil
  end,
  acceptsTextEntry = function() return board ~= nil and board:allowTextEntry() end,
  focusSearch = focusSearch,
  searchHotkeyEnabled = function() return searchHotkey.enabled == true end,
  searchIsFocused = function(callback)
    if not board then return callback(false) end
    board:evaluateJavaScript(
      "document.activeElement?.getAttribute('placeholder') === 'Search (⌘K)...'",
      function(result) callback(result == true) end
    )
  end,
}

hs.hotkey.bind({ "alt" }, "k", toggleBoard)
