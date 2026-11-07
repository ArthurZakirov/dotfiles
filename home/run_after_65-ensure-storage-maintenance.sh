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
backup="$HOME/.local/state/storage-maintenance"
saved_plist="$backup/$label.last-good.plist"
saved_script="$backup/$label.last-good.py"
saved_hash="$backup/$label.last-good.sha256"

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

# Only replace a loaded job when we can restore a verified working version.
# The run_before_02 hook captures that version before chezmoi writes new files.
if [ "$active" -eq 1 ]; then
  [ -f "$saved_plist" ] && [ -f "$saved_script" ] && [ -f "$saved_hash" ] || {
    echo "storage-maintenance: no recovery snapshot; run a full chezmoi apply" >&2
    exit 1
  }
  saved_revision="$(cat "$saved_plist" "$saved_script" | shasum -a 256 | awk '{print $1}')"
  [ "$saved_revision" = "$(cat "$saved_hash")" ] || {
    echo "storage-maintenance: recovery snapshot checksum mismatch; refusing restart" >&2
    exit 1
  }
  launchctl bootout "$service"
fi

if ! launchctl bootstrap "$domain" "$plist"; then
  if [ "$active" -eq 1 ]; then
    # Restore both the old script and the plist. This also survives next login
    # and leaves chezmoi diff reporting the intended update as not applied.
    cp "$saved_script" "$script"
    cp "$saved_plist" "$plist"
    if launchctl bootstrap "$domain" "$plist"; then
      echo "storage-maintenance: update failed; previous job restored" >&2
    else
      echo "storage-maintenance: update AND restoration failed; manual intervention required" >&2
    fi
  else
    echo "storage-maintenance: first installation failed; no previous job" >&2
  fi
  exit 1
fi

temporary="$(mktemp "$marker.XXXXXX")"
printf '%s\n' "$desired" > "$temporary"
mv "$temporary" "$marker"
echo "storage-maintenance: loaded managed Chrome-clone cleaner"
