#!/bin/bash
# Launch an interactive workflow in a new macOS Terminal session.
# Keep this outside scripts/ so Raycast indexes only the named wrappers.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s {chezmoi-diff|chezmoi-apply|chezmoi-update|sync-systemsmith}\n' "$0" >&2
  exit 2
fi

case "$1" in
  chezmoi-diff) command='chezmoi diff' ;;
  chezmoi-apply) command='chezmoi apply' ;;
  chezmoi-update) command='chezmoi update' ;;
  # The alias is defined in the interactive ~/.zshrc, not in this file.
  sync-systemsmith) command='zsh -ic sync-systemsmith' ;;
  *)
    printf 'Unknown Raycast workflow: %s\n' "$1" >&2
    exit 2
    ;;
esac

# osascript receives the fixed command as an argv value, not embedded AppleScript.
# Terminal's do script creates a new session with output and stdin visible.
osascript - "$command" <<'APPLESCRIPT'
on run argv
  tell application "Terminal"
    activate
    do script (item 1 of argv)
  end tell
end run
APPLESCRIPT
