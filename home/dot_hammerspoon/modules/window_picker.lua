local HYPER = AgentDesk.hyper

local function pickWindow()
  -- Mission Control swallows every keystroke, so the chooser would open but
  -- never hear the typing. Leave Mission Control first, then show it.
  hs.spaces.closeMissionControl()

  local chooser = hs.chooser.new(function(choice)
    if not choice then return end
    local w = hs.window.get(choice.wid)
    if w then w:focus() end
  end)

  local rows = {}
  for _, app in ipairs(hs.application.runningApplications()) do
    if app:kind() == 1 then -- regular GUI apps only
      for _, w in ipairs(app:allWindows()) do
        if w:isStandard() and w:title() ~= "" then
          rows[#rows + 1] = {
            text = w:title(),
            subText = app:name() .. "  \u{2014}  " .. (w:screen() and w:screen():name() or ""),
            wid = w:id(),
            image = hs.image.imageFromAppBundle(app:bundleID() or ""),
          }
        end
      end
    end
  end
  chooser:choices(rows)
  chooser:searchSubText(true)
  -- Small delay so the Mission Control exit animation is done grabbing input.
  hs.timer.doAfter(0.25, function() chooser:show() end)
end

-- Ö is reserved for display four; / opens the cross-space window picker.
hs.hotkey.bind(HYPER, "/", pickWindow)
