#!/bin/bash
set -euo pipefail

# Never launch a GUI app in optional-app CI or without an active macOS GUI session.
[[ "${DOTFILES_SKIP_OPTIONAL_APPS:-0}" == "1" ]] && exit 0
[[ "$(uname -s)" == "Darwin" ]] || exit 0

app="${HAMMERSPOON_APP_PATH:-/Applications/Hammerspoon.app}"
verify="${HAMMERSPOON_VERIFY_BIN:-$HOME/.local/bin/hammerspoon-verify}"
swift_setup="${HAMMERSPOON_SWIFTC_HELPER:-$HOME/.local/bin/hammerspoon-ensure-swiftc}"
if [[ ! -d "$app" ]]; then
  printf 'Hammerspoon: not installed; skipping launch.\n'
  exit 0
fi
if ! launchctl print "gui/$(id -u)" >/dev/null 2>&1; then
  printf 'Hammerspoon: no GUI login session; skipping launch.\n'
  exit 0
fi

# Provision Swift for the microphone meter; failure is retried on first use.
if [[ -x "$swift_setup" ]] && ! "$swift_setup" >/dev/null; then
  printf 'Hammerspoon: Swift setup incomplete; will retry during audio check.\n' >&2
fi

# Only launch when absent. Never kill, restart, or reload a running instance.
if ! pgrep -x Hammerspoon >/dev/null 2>&1; then
  open -a "$app"
fi

# Non-destructive, time-bounded check. A missing permission or IPC response
# is actionable feedback, not grounds to fail a chezmoi apply.
if [[ -x "$verify" ]] && ! "$verify"; then
  printf 'Hammerspoon: automatic verification incomplete; see output above.\n' >&2
fi
