#!/bin/sh
# Adopt the existing local-only cleaner into chezmoi management. Reapply safely.
set -eu
[ "$(uname -s)" = "Darwin" ] || exit 0

label=com.arthur.storage-maintenance
domain="gui/$(id -u)"
service="$domain/$label"
plist="$HOME/Library/LaunchAgents/$label.plist"
script="$HOME/.local/share/storage-maintenance/clean_chrome_clones.py"
marker="$HOME/Library/Caches/chezmoi/$label.sha256"

[ -f "$plist" ] && [ -f "$script" ] || {
  echo "storage-maintenance: managed plist or script missing" >&2
  exit 1
}
plutil -lint "$plist" >/dev/null
/usr/bin/python3 - "$script" <<'PYTHON'
import ast
from pathlib import Path
import sys
ast.parse(Path(sys.argv[1]).read_text())
PYTHON
mkdir -p "$HOME/Library/Logs" "$(dirname "$marker")"
# GUI service cannot be loaded during a headless install.
if ! launchctl print "$domain" >/dev/null 2>&1; then
  echo "storage-maintenance: no GUI domain; service will load on login"
  exit 0
fi

desired="$(cat "$plist" "$script" | shasum -a 256 | awk '{print $1}')"
active=0
if launchctl print "$service" >/dev/null 2>&1; then active=1; fi
if [ "$active" -eq 1 ] && [ -f "$marker" ] && [ "$(cat "$marker")" = "$desired" ]; then
  exit 0
fi

# Reuse existing launchd label; no duplicate worker.
if [ "$active" -eq 1 ]; then launchctl bootout "$service"; fi
launchctl bootstrap "$domain" "$plist"
temporary="$(mktemp "$marker.XXXXXX")"
printf '%s\n' "$desired" > "$temporary"
mv "$temporary" "$marker"
echo "storage-maintenance: loaded managed Chrome-clone cleaner"
