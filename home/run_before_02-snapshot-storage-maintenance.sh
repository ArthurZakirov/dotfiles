#!/bin/sh
# Preserve the currently loaded Chrome-cleaner job BEFORE chezmoi overwrites it.
set -eu
[ "$(uname -s)" = "Darwin" ] || exit 0

label=com.arthur.storage-maintenance
service="gui/$(id -u)/$label"
plist="$HOME/Library/LaunchAgents/$label.plist"
script="$HOME/.local/share/storage-maintenance/clean_chrome_clones.py"
marker="$HOME/Library/Caches/chezmoi/$label.sha256"
backup="$HOME/.local/state/storage-maintenance"

# No previous service to recover on a fresh installation.
launchctl print "$service" >/dev/null 2>&1 || exit 0
[ -f "$plist" ] && [ -f "$script" ] || exit 0

current="$(cat "$plist" "$script" | shasum -a 256 | awk '{print $1}')"
# A stale marker means files might already have been overwritten by an earlier
# failed apply. Do not overwrite the last-known-good snapshot with them.
if [ -f "$marker" ] && [ "$(cat "$marker")" != "$current" ]; then
  echo "storage-maintenance: installed files do not match the active revision; retaining prior snapshot" >&2
  exit 0
fi

mkdir -p "$backup"
tmp_plist="$(mktemp "$backup/plist.XXXXXX")"
tmp_script="$(mktemp "$backup/script.XXXXXX")"
tmp_hash="$(mktemp "$backup/hash.XXXXXX")"
trap 'rm -f "$tmp_plist" "$tmp_script" "$tmp_hash"' EXIT
cp "$plist" "$tmp_plist"
cp "$script" "$tmp_script"
printf '%s\n' "$current" > "$tmp_hash"
mv "$tmp_plist" "$backup/$label.last-good.plist"
mv "$tmp_script" "$backup/$label.last-good.py"
# Write hash LAST; an interrupted snapshot is invalidated by its checksum.
mv "$tmp_hash" "$backup/$label.last-good.sha256"
