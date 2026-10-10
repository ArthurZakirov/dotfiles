#!/bin/bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)/src/apps.sh"

calls=()
brew() {
  if [[ "$1" == list ]]; then
    [[ "${BREW_INSTALLED:-}" == "$3" ]]
  else
    calls+=("$*")
  fi
}
app_exists() { [[ "${APP_INSTALLED:-}" == "$1" ]]; }
command() {
  if [[ "$1" == -v ]]; then
    [[ "${CLI_INSTALLED:-}" == "$2" ]]
  else
    builtin command "$@"
  fi
}

# A cask registered with Homebrew is not reinstalled.
BREW_INSTALLED=alt-tab
install_missing_cask alt-tab AltTab.app
[[ ${#calls[@]} -eq 0 ]]
unset BREW_INSTALLED

# A manually installed app is not reinstalled.
APP_INSTALLED=AltTab.app
install_missing_cask alt-tab AltTab.app
[[ ${#calls[@]} -eq 0 ]]
unset APP_INSTALLED

# A missing app is installed through Homebrew.
install_missing_cask alt-tab AltTab.app
[[ ${calls[0]} == 'install --cask alt-tab' ]]

# Existing CLIs are not reinstalled, regardless of installation method.
CLI_INSTALLED=codex
calls=()
install_missing_cli_cask codex codex
install_missing_formula codex codex
[[ ${#calls[@]} -eq 0 ]]
unset CLI_INSTALLED

# Missing CLIs use their specified packages.
install_missing_cli_cask claude claude-code
install_missing_formula node node
[[ "${calls[*]}" == 'install --cask claude-code install node' ]]

echo 'app installer: 5 skip/install checks passed (no installers executed)'
