#!/usr/bin/env bash
# Load the persistent browser for the current GUI session; launchd starts it on future logins.
set -euo pipefail
[[ "$(uname -s)" == "Darwin" ]] || exit 0

label="com.arthur.agent-backlog"
plist="$HOME/Library/LaunchAgents/$label.plist"
domain="gui/$(id -u)"
if ! launchctl print "$domain" >/dev/null 2>&1; then
  echo "Agent Backlog: no GUI login session; launchd will start it on next login."
  exit 0
fi
[[ -f "$plist" ]] || { echo "Agent Backlog: missing $plist" >&2; exit 1; }
if launchctl print "$domain/$label" >/dev/null 2>&1; then
  launchctl bootout "$domain/$label"
fi

# launchd may still be releasing the previous job immediately after bootout.
for attempt in 1 2 3 4 5; do
  if launchctl bootstrap "$domain" "$plist" >/dev/null 2>&1; then
    echo "Agent Backlog: loaded current persistent localhost service configuration."
    exit 0
  fi
  sleep 1
done
launchctl bootstrap "$domain" "$plist" # Expose the actual error after retries.
