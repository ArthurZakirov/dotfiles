#!/bin/bash
set -euo pipefail

# Never launch a GUI app in optional-app CI or without an active macOS GUI session.
[[ "${DOTFILES_SKIP_OPTIONAL_APPS:-0}" == "1" ]] && exit 0
[[ "$(uname -s)" == "Darwin" ]] || exit 0

app="${HAMMERSPOON_APP_PATH:-/Applications/Hammerspoon.app}"
activate="${HAMMERSPOON_ACTIVATE_BIN:-$HOME/.local/bin/hammerspoon-activate}"
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

# Reconcile both states: start when stopped, or reload when already running.
# A failed readiness check must be visible as a failed apply, not false success.
if [[ ! -x "$activate" ]]; then
  printf 'Hammerspoon: activation helper missing: %s\n' "$activate" >&2
  exit 1
fi
if [ -r "$(chezmoi source-path | sed 's@/home$@@')/src/provisioning-log.sh" ]; then
  source "$(chezmoi source-path | sed 's@/home$@@')/src/provisioning-log.sh"
  dotfiles_section "HAMMERSPOON RUNTIME"
fi
"$activate"
