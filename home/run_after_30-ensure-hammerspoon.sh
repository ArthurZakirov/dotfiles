#!/bin/bash
set -euo pipefail

# Never launch a GUI app without an active macOS GUI session.
[[ "$(uname -s)" == "Darwin" ]] || exit 0

app="${HAMMERSPOON_APP_PATH:-/Applications/Hammerspoon.app}"
activate="${HAMMERSPOON_ACTIVATE_BIN:-$HOME/.local/bin/hammerspoon-activate}"
if [[ ! -d "$app" ]]; then
  printf 'Hammerspoon: not installed; skipping launch.\n'
  exit 0
fi
if ! launchctl print "gui/$(id -u)" >/dev/null 2>&1; then
  printf 'Hammerspoon: no GUI login session; skipping launch.\n'
  exit 0
fi

# Swift belongs to the microphone meter and is provisioned on first use,
# not during every chezmoi apply (which also holds the state lock).

# Reconcile both states: start when stopped, or reload when already running.
# A failed readiness check must be visible as a failed apply, not false success.
if [[ ! -x "$activate" ]]; then
  printf 'Hammerspoon: activation helper missing: %s\n' "$activate" >&2
  exit 1
fi
printf '\n  -- HAMMERSPOON --\n'
"$activate"
