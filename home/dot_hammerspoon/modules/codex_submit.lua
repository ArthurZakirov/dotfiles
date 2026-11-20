-- Deliver directly to the Codex process holding the dictation microphone.
-- A missing listener (including older releases) must never synthesize Enter.
local config = hs.json.read(os.getenv("HOME") .. "/.config/codex-voice/config.json") or {}
local shortcut = config.global_submit_shortcut
if shortcut == nil then shortcut = "alt-shift-return" end
if shortcut == false then return end
local mods = {}
local key
local modifiers = { ctrl = true, cmd = true, alt = true, shift = true }
if type(shortcut) == "string" then
  for part in shortcut:gmatch("[^-]+") do
    if modifiers[part] and not key then
      table.insert(mods, part)
    elseif not key then
      key = part
    else
      key = nil
      break
    end
  end
end
if not key or not hs.keycodes.map[key] or #mods == 0 then
  hs.alert.show("Invalid Codex global_submit_shortcut")
  return
end

local task
local function submit()
  if task and task:isRunning() then return end
  task = hs.task.new("/usr/bin/python3", function(code)
    task = nil
    if code ~= 0 then hs.alert.show("No Codex dictation receiver available") end
  end, { "-c", [[
import os, socket
with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
    client.settimeout(0.5)
    client.sendto(b"submit", os.path.expanduser("~/.codex/voice-submit.sock"))
]] })
  task:start()
end
hs.hotkey.bind(mods, key, submit)
