local M = {}

local TEST_SOUND = "/System/Library/Sounds/Ping.aiff"
local MIC_METER = hs.configdir .. "/bin/mic_level"
local MIN_OUTPUT_VOLUME = 10 -- Below this level, warn instead of showing green.
local EXPECTED_OUTPUT = "Arctis Nova 7 Gen 2"
local VALID_INPUTS = {
  ["Arctis Nova 7 Gen 2"] = true,
  ["HD Pro Webcam C920"] = true,
}

local card
local micTask
local closeTimer
local testSound
local micIconIndex
local micValueIndex
local inputMuteIconIndex
local inputMuteValueIndex
local signalDetected = false
local streamBuffer = ""

local COLORS = {
  white = { white = 0.95 },
  muted = { white = 0.58 },
  green = { red = 0.34, green = 0.86, blue = 0.48 },
  red = { red = 1.0, green = 0.32, blue = 0.32 },
  blue = { red = 0.48, green = 0.76, blue = 1.0 },
}

local function stopPreviousRun()
  if closeTimer then closeTimer:stop(); closeTimer = nil end
  if micTask and micTask:isRunning() then micTask:terminate() end
  micTask = nil
  if card then card:delete(); card = nil end
end

local function emojiText(symbol)
  return hs.styledtext.new(symbol, {
    font = { name = "Apple Color Emoji", size = 22 },
  })
end

local function statusSymbol(ok)
  if ok == nil then return "⏳" end
  return ok and "✅" or "❗"
end

local function statusColor(ok)
  if ok == nil then return COLORS.blue end
  return ok and COLORS.green or COLORS.red
end

local function addText(elements, text, x, y, w, h, size, color, font)
  elements[#elements + 1] = {
    type = "text",
    text = text,
    textSize = size,
    textFont = font or ".AppleSystemUIFont",
    textColor = color,
    textAlignment = "left",
    frame = { x = x, y = y, w = w, h = h },
  }
  return #elements
end

local function addRow(elements, y, ok, label, value)
  elements[#elements + 1] = {
    type = "text",
    text = emojiText(statusSymbol(ok)),
    frame = { x = 30, y = y - 1, w = 34, h = 30 },
  }
  local iconIndex = #elements
  addText(elements, label, 72, y, 170, 28, 17, COLORS.white)
  local valueIndex = addText(elements, value, 245, y, 335, 28, 17, statusColor(ok))
  return iconIndex, valueIndex
end

local function showCard(output, input)
  local screen = hs.mouse.getCurrentScreen() or hs.screen.mainScreen()
  local frame = screen:frame()
  local width, height = 620, 550
  local elements = {
    {
      type = "rectangle",
      action = "fill",
      roundedRectRadii = { xRadius = 26, yRadius = 26 },
      fillColor = { red = 0.045, green = 0.047, blue = 0.06, alpha = 0.96 },
    },
  }

  addText(elements, "Audio-Test", 30, 20, 560, 38, 27, COLORS.white)
  addText(elements, "🎧 AUSGABE", 30, 72, 560, 25, 13, COLORS.muted)

  local outputName = output and output:name() or "Kein Gerät"
  local outputVolume = output and output:outputVolume() or nil
  local outputMuted = output and output:outputMuted() or nil
  local expectedOutputConnected = false
  for _, device in ipairs(hs.audiodevice.allOutputDevices()) do
    if device:name() == EXPECTED_OUTPUT then expectedOutputConnected = true; break end
  end
  addRow(elements, 104, expectedOutputConnected, "Verbindung",
    expectedOutputConnected and "Arctis-Dongle erkannt" or "Arctis-Dongle nicht erkannt")
  addRow(elements, 140, outputName == EXPECTED_OUTPUT, "Ausgang", outputName)
  local volumeLabel = "Nicht verfügbar"
  if outputVolume ~= nil then
    if outputVolume == 0 then
      volumeLabel = "0% — Keine Lautstärke"
    elseif outputVolume < MIN_OUTPUT_VOLUME then
      volumeLabel = string.format("%.1f%% — Sehr leise (< %d%%)", outputVolume, MIN_OUTPUT_VOLUME)
    else
      volumeLabel = string.format("%.0f%%", outputVolume)
    end
  end
  addRow(elements, 176, outputVolume ~= nil and outputVolume >= MIN_OUTPUT_VOLUME,
    "Lautstärke", volumeLabel)
  addRow(elements, 212, outputMuted ~= true,
    "Stummschaltung", outputMuted and "Stumm" or "Nicht stumm")

  elements[#elements + 1] = {
    type = "segments",
    action = "stroke",
    strokeColor = { white = 0.18 },
    strokeWidth = 1,
    coordinates = { { x = 30, y = 262 }, { x = 590, y = 262 } },
  }

  addText(elements, "🎤 EINGABE", 30, 286, 560, 25, 13, COLORS.muted)

  local inputName = input and input:name() or "Kein Gerät"
  local inputVolume = input and input:inputVolume() or nil
  local inputMuted = input and input:inputMuted() or nil
  addRow(elements, 318, VALID_INPUTS[inputName] == true, "Gerät", inputName)
  addRow(elements, 354, inputVolume ~= nil and inputVolume > 0,
    "Eingangspegel", inputVolume and string.format("%.0f%%", inputVolume) or "Nicht verfügbar")
  inputMuteIconIndex, inputMuteValueIndex = addRow(
    elements,
    390,
    inputMuted == nil and nil or not inputMuted,
    "Stummschaltung",
    inputMuted == nil and "Wird durch Mikrofontest geprüft" or (inputMuted and "Stumm" or "Nicht stumm")
  )
  micIconIndex, micValueIndex = addRow(
    elements, 426, nil, "Mikrofontest", "Nach dem Ping sprechen oder klatschen …")

  addText(elements,
    "Alles grün, aber kein Ping: Headset-Power, Funk und Lautstärkerad prüfen.\n"
      .. "Der physische Mic-Mute-Schalter ist nur über den Mikrofontest prüfbar.",
    30, 486, 560, 46, 13, COLORS.muted)

  card = hs.canvas.new({
    x = frame.x + (frame.w - width) / 2,
    y = frame.y + (frame.h - height) / 2,
    w = width,
    h = height,
  })
  card:appendElements(table.unpack(elements))
  card:level(hs.canvas.windowLevels.overlay)
  card:show(0.12)
end

local function setMicResult(ok, message)
  if not card then return end
  card[micIconIndex].text = emojiText(statusSymbol(ok))
  card[micValueIndex].text = message
  card[micValueIndex].textColor = statusColor(ok)
end

local function setInputMuteResult(ok, message)
  if not card then return end
  card[inputMuteIconIndex].text = emojiText(statusSymbol(ok))
  card[inputMuteValueIndex].text = message
  card[inputMuteValueIndex].textColor = statusColor(ok)
end

local function scheduleClose()
  if closeTimer then closeTimer:stop() end
  closeTimer = hs.timer.doAfter(2.5, function()
    if card then card:delete(); card = nil end
    closeTimer = nil
  end)
end

local function processMicOutput(chunk)
  streamBuffer = streamBuffer .. (chunk or "")
  while true do
    local line, rest = streamBuffer:match("^([^\n]*)\n(.*)$")
    if not line then break end
    streamBuffer = rest
    local level = tonumber(line)
    if level and not signalDetected then
      setMicResult(nil, string.format("Höre zu … Pegel %.0f%%", math.min(level * 500, 100)))
      -- The visible meter maps an RMS value of 0.002 to 1%. Normal speech on
      -- the Arctis microphone reaches roughly 1–2%, so count 0.75% and above
      -- as a real signal while leaving the observed idle noise below it.
      if level >= 0.0015 then
        signalDetected = true
        setInputMuteResult(true, "Nicht stumm – Signal erkannt")
        setMicResult(true, "Signal erkannt")
        if micTask and micTask:isRunning() then micTask:terminate() end
      end
    end
  end
end

local function startMicTest(input)
  if not input then
    setMicResult(false, "Kein Eingabegerät erkannt")
    scheduleClose()
    return
  end

  signalDetected = false
  streamBuffer = ""
  micTask = hs.task.new(
    MIC_METER,
    function(exitCode, _, stdErr)
      if signalDetected then
        scheduleClose()
        return
      end
      if exitCode == 0 then
        setInputMuteResult(false, "Kein Signal – Mic-Mute prüfen")
        setMicResult(false, "Kein Signal erkannt")
      elseif stdErr and stdErr:find("nicht erlaubt", 1, true) then
        setMicResult(false, "Mikrofonzugriff für Hammerspoon erlauben")
      else
        setMicResult(false, "Mikrofontest konnte nicht starten")
      end
      scheduleClose()
    end,
    function(_, stdOut, _)
      processMicOutput(stdOut)
      return not signalDetected
    end
  )

  if not micTask or not micTask:start() then
    setMicResult(false, "Mikrofontest konnte nicht starten")
    scheduleClose()
  end
end


function M.run()
  stopPreviousRun()

  local output = hs.audiodevice.defaultOutputDevice()
  local input = hs.audiodevice.defaultInputDevice()
  showCard(output, input)

  if output then
    testSound = hs.sound.getByFile(TEST_SOUND)
    if testSound then
      testSound:device(output:uid())
      testSound:play()
    end
  end

  hs.timer.doAfter(0.8, function() startMicTest(input) end)
end

return M
