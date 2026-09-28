#!/bin/sh
set -eu

[ "$(uname -s)" = "Darwin" ] || exit 0

label='com.arthur.desktop-commander-remote'
plist="$HOME/Library/LaunchAgents/$label.plist"
domain="gui/$(id -u)"
service="$domain/$label"
cache_dir="$HOME/Library/Caches/chezmoi"
marker="$cache_dir/$label.sha256"

mkdir -p "$cache_dir"
plutil -lint "$plist" >/dev/null

current_hash="$(shasum -a 256 "$plist" | awk '{print $1}')"
previous_hash="$(cat "$marker" 2>/dev/null || true)"

if launchctl print "$service" >/dev/null 2>&1; then
  if [ "$previous_hash" != "$current_hash" ]; then
    launchctl bootout "$domain" "$plist" >/dev/null 2>&1 || true
    launchctl bootstrap "$domain" "$plist"
  fi
else
  launchctl bootstrap "$domain" "$plist"
fi

printf '%s\n' "$current_hash" > "$marker"
