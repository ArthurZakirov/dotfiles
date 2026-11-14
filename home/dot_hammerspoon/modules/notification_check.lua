local settingsURL = "x-apple.systempreferences:com.apple.Notifications-Settings.extension"
local predicate = 'process == "NotificationCenter" AND eventMessage CONTAINS "muted by display state (displayShared)"'
local pending

local function recordingStatus()
  local app = hs.application.get("com.apple.controlcenter")
  if not app then return "Kontrollzentrum nicht erreichbar." end

  local menu = hs.axuielement.applicationElement(app).AXExtrasMenuBar
  for _, item in ipairs(menu and menu.AXChildren or {}) do
    if item.AXIdentifier == "com.apple.menuextra.controlcenter" then
      local description = item.AXDescription or ""
      if description:find("Screen Recording is in use", 1, true)
        or description:find("Bildschirmaufnahme wird verwendet", 1, true) then
        return "Aktuell meldet das Kontrollzentrum eine Bildschirmaufnahme."
      end
    end
  end
  return "Aktuelle Bildschirmaufnahme nicht bestätigt."
end

local function showResult(exitCode, output)
  pending = nil
  local lastBlocked
  for timestamp in output:gmatch("(%d%d%d%d%-%d%d%-%d%d %d%d:%d%d:%d%d)[^\n]*muted by display state %(displayShared%)") do
    lastBlocked = timestamp
  end

  local headline = "⚪ Blockade nicht bestätigt"
  local detail = "In den letzten 15 Minuten wurde keine passende Unterdrückung protokolliert."
  if exitCode ~= 0 then
    detail = "Das macOS-Mitteilungsprotokoll konnte nicht gelesen werden."
  elseif lastBlocked then
    headline = "❌ Mitteilung bei Bildschirmfreigabe unterdrückt"
    detail = "Letzter bestätigter Treffer: " .. lastBlocked .. "."
  end

  local message = detail .. "\n" .. recordingStatus()
    .. "\n\nMitteilungen → Bei Spiegelung oder Freigabe des Displays → Mitteilungen erlauben."
  if hs.dialog.blockAlert(headline, message, "Einstellungen öffnen", "Schließen") == "Einstellungen öffnen" then
    hs.urlevent.openURL(settingsURL)
  end
end

hs.hotkey.bind(HammerspoonConfig.hyper, "n", function()
  if pending then return end
  pending = hs.task.new("/usr/bin/log", showResult, {
    "show", "--last", "15m", "--style", "compact", "--predicate", predicate,
  })
  if not pending or not pending:start() then
    showResult(1, "")
  end
end)
