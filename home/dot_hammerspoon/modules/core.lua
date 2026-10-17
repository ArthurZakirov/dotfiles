local AD = AgentDesk

local function noModsHeld()
  local flags = hs.eventtap.checkKeyboardModifiers()
  return not (flags.ctrl or flags.alt or flags.cmd or flags.shift or flags.fn)
end

local function afterModsReleased(fn)
  if noModsHeld() then
    fn()
    return
  end

  hs.timer.waitUntil(noModsHeld, function()
    hs.timer.doAfter(0.05, fn)
  end, 0.05)
end

AD.afterModsReleased = afterModsReleased
