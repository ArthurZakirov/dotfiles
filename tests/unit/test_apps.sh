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

# Peekaboo already available on PATH is not reinstalled.
CLI_INSTALLED=peekaboo
calls=()
install_missing_formula peekaboo openclaw/tap/peekaboo
[[ ${#calls[@]} -eq 0 ]]
unset CLI_INSTALLED

# Vercel's skills CLI is explicitly provisioned (not just fetched by npx).
skills() { [[ "$1" == --version ]] && [[ "${SKILLS_VERSION_FAIL:-0}" == 0 ]]; }
npm() { calls+=("npm $*"); [[ "${NPM_FAIL:-0}" == 0 ]]; }
CLI_INSTALLED=skills
calls=()
install_skills_cli
[[ ${#calls[@]} -eq 0 ]]
unset CLI_INSTALLED
install_skills_cli
[[ "${calls[*]}" == 'npm install --global skills' ]]
SKILLS_VERSION_FAIL=1
if install_skills_cli 2>/dev/null; then exit 1; fi
unset SKILLS_VERSION_FAIL
NPM_FAIL=1
if install_skills_cli 2>/dev/null; then exit 1; fi
unset NPM_FAIL
calls=()

# npm-backed agent-browser is installed only if missing and verified.
agent-browser() { [[ "$1" == --version ]] && [[ "${BROWSER_VERSION_FAIL:-0}" == 0 ]]; }
npm() { calls+=("npm $*"); [[ "${NPM_FAIL:-0}" == 0 ]]; }
CLI_INSTALLED=agent-browser
calls=()
install_agent_browser_cli
[[ ${#calls[@]} -eq 0 ]]
unset CLI_INSTALLED
install_agent_browser_cli
[[ "${calls[*]}" == 'npm install --global agent-browser' ]]
BROWSER_VERSION_FAIL=1
if install_agent_browser_cli 2>/dev/null; then exit 1; fi
unset BROWSER_VERSION_FAIL
NPM_FAIL=1
if install_agent_browser_cli 2>/dev/null; then exit 1; fi
unset NPM_FAIL
calls=()

# Missing CLIs use their specified packages.
install_missing_cli_cask claude claude-code
install_missing_formula node node
install_missing_formula peekaboo openclaw/tap/peekaboo
[[ "${calls[*]}" == 'install --cask claude-code install node install openclaw/tap/peekaboo' ]]

echo 'app installer: browser/skills CLIs and 6 skip/install checks passed (no installers executed)'
