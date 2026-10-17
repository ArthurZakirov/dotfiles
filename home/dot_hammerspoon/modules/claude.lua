------------------------------------------------------- claude sidebar (via AX)

local HYPER = AgentDesk.hyper
local afterModsReleased = AgentDesk.afterModsReleased

-- Claude's Code tab is a web UI, and Chromium only builds its accessibility
-- tree once an assistive client asks for it. Until AXManualAccessibility is
-- set, the whole window exposes ~40 empty nodes: no sidebar, no session rows,
-- no menus. With it set, the sidebar's group headers and each session's "more
-- options" menu become addressable, which is the only keyboard route to
-- collapsing a group or moving a session between groups.
local function claudeWindow()
  local app = hs.application.get("Claude")
  if not app then return nil end
  local ax = hs.axuielement.applicationElement(app)
  if not ax then return nil end
  ax:setAttributeValue("AXManualAccessibility", true)
  local wins = ax:attributeValue("AXWindows")
  return wins and wins[1], app
end

-- Everything below stays inside the sidebar subtree on purpose: the full window
-- is ~3.7k nodes, and walking that on Hammerspoon's main thread stalls every
-- other hotkey for seconds.
local function claudeSidebar()
  local win, app = claudeWindow()
  if not win then return nil end
  local found
  local function walk(el, d)
    -- The sidebar is virtualised: rows are created and destroyed while the
    -- walk runs, so AXChildren can hand back a nil entry.
    if not el or d > 20 or found then return end
    if el:attributeValue("AXDescription") == "Sidebar" then found = el return end
    local kids = el:attributeValue("AXChildren")
    if kids then for _, c in ipairs(kids) do walk(c, d + 1) end end
  end
  walk(win, 0)
  return found, app
end

local function collectIn(root, pred)
  local out = {}
  local function walk(el, d)
    if not el or d > 18 then return end
    if pred(el) then out[#out + 1] = el end
    local kids = el:attributeValue("AXChildren")
    if kids then for _, c in ipairs(kids) do walk(c, d + 1) end end
  end
  if root then walk(root, 0) end
  return out
end

-- Session rows are buttons whose title carries a status prefix ("Idle Fix the
-- parser"); group headers are the remaining titled buttons, minus the sidebar's
-- own controls.
local SIDEBAR_CONTROLS = { New = true, Customize = true, Search = true }

local function isClaudeSession(el)
  local t = el:attributeValue("AXTitle")
  return el:attributeValue("AXRole") == "AXButton" and type(t) == "string"
     and (t:match("^Idle ") or t:match("^Error ") or t:match("^Running ")
          or t:match("^Waiting ") or t:match("^Queued "))
end

-- The sidebar parks transient buttons among the headers, notably the
-- "Relaunch to update vX.Y" banner. Folding every group must not press that
-- one: it restarts the app mid-session.
local function isClaudeGroupHeader(el)
  local t = el:attributeValue("AXTitle")
  if el:attributeValue("AXRole") ~= "AXButton"
     or type(t) ~= "string" or #t == 0 then return false end
  if SIDEBAR_CONTROLS[t] or t:match("^Relaunch") or t:match("^Update") then
    return false
  end
  return not isClaudeSession(el)
end

-- Pick a group by name and fold/unfold it.
local function claudeToggleGroup()
  local sidebar = claudeSidebar()
  if not sidebar then hs.alert.show("Claude sidebar not found") return end
  local headers = collectIn(sidebar, isClaudeGroupHeader)
  if #headers == 0 then hs.alert.show("No Claude groups found") return end

  local choices = {}
  for i, el in ipairs(headers) do
    choices[i] = { text = el:attributeValue("AXTitle"), idx = i }
  end
  hs.chooser.new(function(pick)
    if pick then headers[pick.idx]:performAction("AXPress") end
  end):placeholderText("Toggle Claude group"):choices(choices):show()
end

-- Fold every group at once, the thing the sidebar has no control for at all.
local function claudeToggleAllGroups()
  local sidebar = claudeSidebar()
  if not sidebar then hs.alert.show("Claude sidebar not found") return end
  local headers = collectIn(sidebar, isClaudeGroupHeader)
  for _, el in ipairs(headers) do el:performAction("AXPress") end
  hs.alert.show("Toggled " .. #headers .. " Claude groups")
end

-- Open a session's context menu, the only route to "Move to group". This picks
-- from a chooser rather than acting on the highlighted row because the sidebar
-- marks no row AXSelected -- there is nothing to read the "current" session
-- from. Once the menu opens, its own accelerators take over: P pin, R rename,
-- A archive, and 1-9 to choose a destination group.
local function claudeSessionMenu()
  local sidebar, app = claudeSidebar()
  if not sidebar then hs.alert.show("Claude sidebar not found") return end
  local sessions = collectIn(sidebar, isClaudeSession)
  if #sessions == 0 then hs.alert.show("No Claude sessions found") return end

  local choices, picks, seen = {}, {}, {}
  for _, el in ipairs(sessions) do
    local title = el:attributeValue("AXTitle")
    if title and not seen[title] then
      seen[title] = true
      -- Titles arrive status-prefixed ("Idle Fix the parser"); demote the
      -- status to subtext so what stays searchable is the name the user knows.
      local status, name = title:match("^(%a+)%s+(.*)$")
      picks[#picks + 1] = el
      choices[#choices + 1] =
        { text = name or title, subText = status or "", idx = #picks }
    end
  end

  hs.chooser.new(function(pick)
    if not pick then return end
    if app then app:activate() end
    -- Let the chooser finish closing and Claude come frontmost, or the menu
    -- opens behind it and swallows the keystrokes meant for it.
    hs.timer.doAfter(0.2, function()
      picks[pick.idx]:performAction("AXShowMenu")
    end)
  end):placeholderText("Claude session menu"):choices(choices):show()
end

-- The sliders button at the top of the sidebar opens the view menu: Status,
-- Environment, Group by (Date / Folder / State / Custom groups / None) and
-- Sort by. The app gives it no shortcut, and it is the only route to those
-- settings. Its menu entries are real AXMenuItems, so once it is open the
-- keyboard can walk it.
local function claudeFilterMenu()
  local sidebar, app = claudeSidebar()
  if not sidebar then hs.alert.show("Claude sidebar not found") return end
  -- The description mutates with filter state: "Filter", "Filter (active)"...
  -- so match the prefix, never the exact string.
  local btn = collectIn(sidebar, function(el)
    local d = el:attributeValue("AXDescription")
    return el:attributeValue("AXRole") == "AXPopUpButton"
       and type(d) == "string" and d:match("^Filter")
  end)[1]
  if not btn then hs.alert.show("Claude filter button not found") return end
  if app then app:activate() end
  -- Held modifiers would otherwise leak into the menu's own key handling.
  afterModsReleased(function() btn:performAction("AXPress") end)
end

-- Toggle a pane's full-window state via the ⤢ button in its header -- the app
-- ships no shortcut for it (absent from the Cmd+/ list). Web-page content in
-- the Browser pane can contain buttons literally titled "expand"/"collapse",
-- so only AXDescription is matched: the pane control is an unlabeled button
-- whose description is Expand (or Collapse once the pane is full-window).
local function claudePaneExpand()
  local win = claudeWindow()
  if not win then hs.alert.show("Claude not running") return end
  local btns = {}
  local function walk(el, d)
    if not el or d > 32 then return end
    local desc = el:attributeValue("AXDescription")
    if el:attributeValue("AXRole") == "AXButton"
       and (desc == "Expand" or desc == "Collapse") then
      btns[#btns + 1] = el
    end
    local kids = el:attributeValue("AXChildren")
    if kids then for _, c in ipairs(kids) do walk(c, d + 1) end end
  end
  walk(win, 0)
  if #btns == 0 then
    hs.alert.show("No pane open in Claude")
  elseif #btns == 1 then
    btns[1]:performAction("AXPress")
  else
    -- Several panes open: offer them by rough on-screen position, top to
    -- bottom then left to right, matching how the panes are laid out.
    table.sort(btns, function(a, b)
      local pa = a:attributeValue("AXPosition") or { x = 0, y = 0 }
      local pb = b:attributeValue("AXPosition") or { x = 0, y = 0 }
      if pa.y ~= pb.y then return pa.y < pb.y end
      return pa.x < pb.x
    end)
    local choices = {}
    for i, el in ipairs(btns) do
      local pos = el:attributeValue("AXPosition") or { x = 0, y = 0 }
      choices[i] = {
        text = string.format("%s pane %d", el:attributeValue("AXDescription"), i),
        subText = string.format("header at %d, %d", pos.x, pos.y),
        idx = i,
      }
    end
    hs.chooser.new(function(pick)
      if pick then btns[pick.idx]:performAction("AXPress") end
    end):placeholderText("Which pane?"):choices(choices):show()
  end
end

-- Deliberately NOT on the global HYPER layer. These act on Claude's sidebar and
-- nothing else, so they only exist while Claude is frontmost and cost no other
-- app a combo. ctrl+alt sit next to each other at the bottom left, so the left
-- hand takes the modifiers and the right hand never leaves j/k/p.
-- ctrl+alt is also clear of Claude's own shortcuts, which all use cmd+alt.
-- hs.hotkey logs every enable/disable at info level. Because these hotkeys are
-- armed and disarmed on every focus change, that logging fires constantly --
-- and when a focus change lands while an `hs -c` call is in flight, the log
-- line tries to write back through the same IPC port and Hammerspoon floods
-- with "already recursing" until it wedges. Warnings and errors still show.
hs.hotkey.setLogLevel("warning")

local CLAUDE_MOD = { "ctrl", "alt" }

-- One flat chooser over the sidebar view menu. The menu's shape is DYNAMIC:
-- "Show empty folders" exists only while grouping by Folder, "Clear filters"
-- only while a filter is set, so rows shift around between invocations. The
-- top-level rows ARE exposed as AXMenuItems, so the target row is located by
-- title in the open menu at execution time; only the submenu options are blind
-- arrow-walks, because submenu rows are not exposed to accessibility at all
-- (verified: zero AX hits app-wide with a submenu on screen).
local CLAUDE_VIEW_MENU = {
  { menu = "Status",      options = { "Active", "Archived", "All" } },
  { menu = "Environment", options = { "All environments", "Local", "Cloud", "Remote Control", "Slack" } },
  { menu = "Group by",    options = { "Date", "Folder", "State", "Custom groups", "None" } },
  { menu = "Sort by",     options = { "Alphabetically", "Created time", "Recency" } },
}
-- Rows that act immediately, without a submenu. Only present in some states.
local CLAUDE_VIEW_DIRECT = { "Show empty folders", "Clear filters" }

-- Keystrokes spaced out on a timer chain: the menu is a web UI and drops keys
-- that arrive before it finishes rendering the previous state.
local function keySequence(steps)
  local t = 0
  for _, st in ipairs(steps) do
    t = t + st.after
    hs.timer.doAfter(t, function() hs.eventtap.keyStroke({}, st.key, 0) end)
  end
end

-- Titles of the open menu's top-level rows, in visual order. AXCheckBox is
-- included because toggle rows like "Show empty folders" may carry that role;
-- separators have neither role and are skipped by arrow keys too.
local function claudeMenuRows()
  local app = hs.application.get("Claude")
  if not app then return {} end
  local wins = hs.axuielement.applicationElement(app):attributeValue("AXWindows")
  local win = wins and wins[1]
  local rows = {}
  local function walk(el, d)
    if not el or d > 28 then return end
    local r = el:attributeValue("AXRole")
    local t = el:attributeValue("AXTitle")
    if (r == "AXMenuItem" or r == "AXCheckBox")
       and type(t) == "string" and #t > 0 then
      rows[#rows + 1] = t
    end
    local kids = el:attributeValue("AXChildren")
    if kids then for _, c in ipairs(kids) do walk(c, d + 1) end end
  end
  walk(win, 0)
  return rows
end

local function claudeViewChooser()
  local sidebar, app = claudeSidebar()
  if not sidebar then hs.alert.show("Claude sidebar not found") return end
  local btn = collectIn(sidebar, function(el)
    local d = el:attributeValue("AXDescription")
    return el:attributeValue("AXRole") == "AXPopUpButton"
       and type(d) == "string" and d:match("^Filter")
  end)[1]
  if not btn then hs.alert.show("Claude filter button not found") return end

  local choices = {}
  for _, m in ipairs(CLAUDE_VIEW_MENU) do
    for oi, opt in ipairs(m.options) do
      choices[#choices + 1] = {
        text = m.menu .. " \u{2192} " .. opt,
        subText = "sidebar view menu",
        prefix = m.menu, subpos = oi,
      }
    end
  end
  for _, d in ipairs(CLAUDE_VIEW_DIRECT) do
    choices[#choices + 1] = { text = d, subText = "sidebar view menu", prefix = d }
  end

  hs.chooser.new(function(pick)
    if not pick then return end
    if app then app:activate() end
    -- Wait out both the chooser closing and any still-held modifiers; a held
    -- ctrl would turn the synthetic Down into a Space switch.
    afterModsReleased(function()
      hs.timer.doAfter(0.25, function()
        btn:performAction("AXPress")
        hs.timer.doAfter(0.45, function()
          -- Locate the target row in THIS menu's actual layout.
          local idx
          for i, title in ipairs(claudeMenuRows()) do
            if title:sub(1, #pick.prefix) == pick.prefix then idx = i break end
          end
          if not idx then
            hs.eventtap.keyStroke({}, "escape", 0)
            hs.alert.show('"' .. pick.prefix .. '" is not in the menu right now')
            return
          end
          -- Each level opens with its first row highlighted, so position n
          -- takes n-1 arrows.
          local steps = {}
          for _ = 1, idx - 1 do steps[#steps + 1] = { key = "down", after = 0.18 } end
          steps[#steps + 1] = { key = "return", after = 0.30 }
          if pick.subpos then
            for _ = 1, pick.subpos - 1 do steps[#steps + 1] = { key = "down", after = 0.18 } end
            steps[#steps + 1] = { key = "return", after = 0.25 }
          end
          keySequence(steps)
        end)
      end)
    end)
  end):placeholderText("Claude view: group / sort / filter"):choices(choices):show()
end

-- Toggle dictation. The composer's microphone is an AXCheckBox described
-- "Press and hold to record"; AXPress toggles it, so this starts and stops
-- recording rather than requiring the key to be held.
local function claudeMic()
  local win = claudeWindow()
  if not win then hs.alert.show("Claude not running") return end
  local hit
  local function walk(el, d)
    if not el or hit or d > 32 then return end
    local desc = el:attributeValue("AXDescription")
    if el:attributeValue("AXRole") == "AXCheckBox"
       and type(desc) == "string" and desc:lower():match("record") then
      hit = el
      return
    end
    local kids = el:attributeValue("AXChildren")
    if kids then for _, c in ipairs(kids) do walk(c, d + 1) end end
  end
  walk(win, 0)
  if not hit then hs.alert.show("Claude mic button not found") return end
  local app = hs.application.get("Claude")
  if app then app:activate() end
  hit:performAction("AXPress")
end

-- One toggle for the whole right-hand pane area, whatever happens to be in it.
-- The per-pane shortcuts the app already ships (cmd+shift+B for Browser, and
-- so on) make individual bindings redundant; what is missing is a single key
-- that closes whatever is open and brings it back.
--
-- Each toolbar entry is an AXCheckBox named after its pane, carrying AXValue 1
-- while that pane is open -- so the open one can be found without guessing.
-- Panes opened some other way (a file preview from a link) have no toolbar
-- entry, so those close via the Close control in the pane's own header, found
-- by its position beside the Expand control rather than by its title: web pages
-- inside the Browser pane contain "Close" buttons of their own.
local CLAUDE_PANES = { "Browser", "Terminal", "Diff" }
local claudeLastPane = "Browser"

local function claudeToggleRightPane()
  local win = claudeWindow()
  if not win then hs.alert.show("Claude not running") return end

  local boxes, expands, closes = {}, {}, {}
  local function walk(el, d)
    if not el or d > 32 then return end
    local role = el:attributeValue("AXRole")
    local desc = el:attributeValue("AXDescription")
    if role == "AXCheckBox" and type(desc) == "string" then
      for _, name in ipairs(CLAUDE_PANES) do
        if desc == name then boxes[name] = el end
      end
    elseif role == "AXButton" and (desc == "Expand" or desc == "Collapse") then
      expands[#expands + 1] = el
    elseif role == "AXButton" and desc == "Close" then
      closes[#closes + 1] = el
    end
    local kids = el:attributeValue("AXChildren")
    if kids then for _, c in ipairs(kids) do walk(c, d + 1) end end
  end
  walk(win, 0)

  local app = hs.application.get("Claude")
  if app then app:activate() end

  -- A pane is open if any toolbar entry is checked.
  for _, name in ipairs(CLAUDE_PANES) do
    local box = boxes[name]
    if box and box:attributeValue("AXValue") == 1 then
      claudeLastPane = name
      box:performAction("AXPress")
      return
    end
  end

  -- No toolbar entry is lit, but a pane header is on screen: something without
  -- a toolbar entry is open, so close it via its own header control.
  if #expands > 0 then
    local ep = expands[1]:attributeValue("AXPosition")
    for _, c in ipairs(closes) do
      local cp = c:attributeValue("AXPosition")
      if ep and cp and math.abs(cp.y - ep.y) < 8 and math.abs(cp.x - ep.x) < 90 then
        c:performAction("AXPress")
        return
      end
    end
  end

  -- Nothing open: bring back whichever pane was closed last.
  local box = boxes[claudeLastPane]
  if box then box:performAction("AXPress")
  else hs.alert.show("Claude: no pane to restore") end
end

-- Forward declaration: the palette lists every action, itself included.
local claudeHelp

-- Single source of truth: the hotkeys and the palette are both built from this,
-- so a new entry here gets a key binding and a palette row with no other edits.
-- The icon leads each row so the palette can be scanned instead of read.
local CLAUDE_ACTIONS = {
  { key = "r", icon = "🪟", label = "Right pane: close / bring back",     fn = claudeToggleRightPane },
  { key = "m", icon = "↔️", label = "Expand / collapse a pane",            fn = claudePaneExpand },
  { key = "j", icon = "📚", label = "Fold / unfold all groups",           fn = claudeToggleAllGroups },
  { key = "k", icon = "📂", label = "Toggle one group",                   fn = claudeToggleGroup },
  { key = "l", icon = "⚙️", label = "Open the sidebar view menu",          fn = claudeFilterMenu },
  { key = "o", icon = "🔀", label = "Set grouping, sorting or filter",    fn = claudeViewChooser },
  { key = "p", icon = "🎛️", label = "Session menu: move to group, pin, …", fn = claudeSessionMenu },
  { key = "d", icon = "🎤", label = "Toggle dictation (microphone)",      fn = claudeMic },
  { key = "h", icon = "❓", label = "Show this list",                      fn = function() claudeHelp() end },
}

-- A runnable palette rather than a static cheat sheet: every row executes, so
-- the bindings stop being something to memorise -- type two letters instead.
claudeHelp = function()
  local choices = {}
  for i, a in ipairs(CLAUDE_ACTIONS) do
    choices[i] = {
      text = a.icon .. "  " .. a.label,
      subText = "⌃⌥" .. a.key:upper(),
      idx = i,
    }
  end
  hs.chooser.new(function(pick)
    if not pick then return end
    -- Let the chooser finish closing: several of these drive Claude's own
    -- menus, which will not open while the chooser still holds focus.
    hs.timer.doAfter(0.15, CLAUDE_ACTIONS[pick.idx].fn)
  end):placeholderText("Claude actions"):choices(choices):show()
end

local claudeHotkeys = {}
for _, a in ipairs(CLAUDE_ACTIONS) do
  claudeHotkeys[#claudeHotkeys + 1] = hs.hotkey.new(CLAUDE_MOD, a.key, a.fn)
end

local function setClaudeHotkeys(on)
  for _, hk in ipairs(claudeHotkeys) do
    if on then hk:enable() else hk:disable() end
  end
end

-- Armed/disarmed on app activation, not window focus: hs.window.filter proved
-- unreliable for Claude's Electron windows (it silently stopped emitting focus
-- events, leaving the hotkeys disarmed while Claude was frontmost, and \u{2303}\u{2325}J
-- fell through to the layout as a literal \u{2206}). An application watcher fires on
-- every activation regardless of how the window is implemented.
-- Kept as a global so it is not garbage collected when this file finishes.
claudeAppWatcher = hs.application.watcher.new(function(name, event)
  if name ~= "Claude" then return end
  if event == hs.application.watcher.activated then
    setClaudeHotkeys(true)
  elseif event == hs.application.watcher.deactivated
      or event == hs.application.watcher.terminated then
    setClaudeHotkeys(false)
  end
end)
claudeAppWatcher:start()

-- The watcher only reports changes, so adopt whatever is frontmost right now.
do
  local front = hs.application.frontmostApplication()
  setClaudeHotkeys(front ~= nil and front:name() == "Claude")
end

-- Warm the accessibility tree as soon as Claude appears, so the first hotkey
-- press after a launch does not hit a still-empty tree.
claudeAXWatcher = hs.application.watcher.new(function(name, event)
  if name == "Claude" and event == hs.application.watcher.launched then
    hs.timer.doAfter(4, claudeWindow)
  end
end)
claudeAXWatcher:start()

-- Double-tap RIGHT command to dictate, so the hands never leave the keyboard.
-- Right command specifically: plain ctrl is already macOS dictation, double-tap
-- option opens Claude's own quick-entry window, and the left command is half of
-- every shortcut on the machine -- a double-tap detector there would misfire on
-- any quick cmd+c / cmd+v pair. The right one is otherwise unused.
local RIGHT_CMD_KEYCODE   = 54
local DOUBLE_TAP_SECONDS  = 0.4
local lastRightCmdPress   = 0

claudeMicTap = hs.eventtap.new({ hs.eventtap.event.types.flagsChanged }, function(e)
  if e:getKeyCode() ~= RIGHT_CMD_KEYCODE then return false end
  -- flagsChanged fires on both press and release; only the press carries cmd.
  if not e:getFlags().cmd then return false end

  local now = hs.timer.secondsSinceEpoch()
  if now - lastRightCmdPress < DOUBLE_TAP_SECONDS then
    lastRightCmdPress = 0
    -- Only inside Claude: elsewhere this must stay an ordinary modifier.
    local front = hs.application.frontmostApplication()
    if front and front:name() == "Claude" then
      for _, a in ipairs(CLAUDE_ACTIONS) do
        if a.key == "d" then a.fn() break end
      end
    end
  else
    lastRightCmdPress = now
  end
  -- Never swallow the event: right command must keep working as a modifier.
  return false
end)
claudeMicTap:start()

-- The old cmd+alt+b remap of Claude's cmd+\\ lived here. Removed: it closed the
-- LEFT sidebar, which cmd+. and cmd+b already handle natively. Closing the
-- right-hand panes is what was actually wanted, and the toolbar checkboxes
-- above (\u{2303}\u{2325}B / T / V) toggle those directly, without synthesising a
-- keystroke the German layout cannot produce.

-- Ctrl+scroll page zoom used to live here as a hand-rolled eventtap; it leaked
-- scroll events under fast wheel spins. Replaced by LinearMouse
-- (~/.config/linearmouse/linearmouse.json, scrolling.modifiers control->zoom),
-- which swallows the scroll and sends cmd+plus/minus robustly.
