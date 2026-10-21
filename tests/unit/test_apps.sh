#!/bin/bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
DOTFILES_ROOT="$repo_root"
source "$repo_root/src/apps.sh"
source "$repo_root/src/setup-actions.sh"

# All installers below are stubbed; no system software is modified.
test_dir="$(mktemp -d)"
trap 'rm -rf "$test_dir"' EXIT
HOME="$test_dir/home"
mkdir -p "$HOME" "$test_dir/npm-prefix/bin"
printf '#!/bin/sh\nexit 0\n' > "$test_dir/npm-prefix/bin/desktop-commander"
chmod +x "$test_dir/npm-prefix/bin/desktop-commander"

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
    if [[ "$2" == npm ]]; then return 0; fi
    [[ "${CLI_INSTALLED:-}" == "$2" ]] && {
      [[ "$2" == desktop-commander ]] && printf '%s\n' "$test_dir/npm-prefix/bin/desktop-commander"
      return 0
    }
    return 1
  fi
  builtin command "$@"
}
skills() { [[ "$1" == --version && "${SKILLS_VERSION_FAIL:-0}" == 0 ]]; }
agent-browser() { [[ "$1" == --version && "${BROWSER_VERSION_FAIL:-0}" == 0 ]]; }
npm() {
  if [[ "$1" == prefix ]]; then
    printf '%s\n' "$test_dir/npm-prefix"
    return 0
  fi
  calls+=("npm $*")
  [[ "${NPM_FAIL:-0}" == 0 ]]
}

# A Homebrew-registered cask is not installed twice.
BREW_INSTALLED=alt-tab
install_missing_cask alt-tab AltTab.app
[[ ${#calls[@]} -eq 0 ]]
unset BREW_INSTALLED

# A manually installed GUI app is not replaced with a Homebrew cask.
APP_INSTALLED=AltTab.app
install_optional_brewfile "$repo_root/dependencies/brew/common/gui.Brewfile" >/dev/null
[[ " ${calls[*]} " != *'install --cask alt-tab'* ]]
unset APP_INSTALLED
calls=()

# A missing GUI app is installed using its original cask token.
install_missing_cask alt-tab AltTab.app
[[ "${calls[0]}" == 'install --cask alt-tab' ]]
calls=()

# Existing CLI casks, formulae, and global npm CLIs are skipped.
CLI_INSTALLED=codex
install_missing_cli_cask codex codex
[[ ${#calls[@]} -eq 0 ]]
CLI_INSTALLED=peekaboo
install_missing_formula peekaboo openclaw/tap/peekaboo
[[ ${#calls[@]} -eq 0 ]]
CLI_INSTALLED=skills
install_npm_cli skills skills version
[[ ${#calls[@]} -eq 0 ]]
unset CLI_INSTALLED

# Both profile-independent Brewfile inventories install the exact former packages.
install_optional_brewfile "$repo_root/dependencies/brew/common/cli.Brewfile"
[[ "${calls[*]}" == 'install --cask codex install --cask claude-code install node install openclaw/tap/peekaboo' ]]
calls=()
PENDING_BREW_ACTIONS=()
install_optional_brewfile "$repo_root/dependencies/brew/common/gui.Brewfile"
[[ "${PENDING_BREW_ACTIONS[*]}" == 'vscode-cli' ]]
[[ "${calls[*]}" == 'install --cask alt-tab install --cask betterdisplay install --cask displaylink install --cask ddpm install --cask warp install --cask google-drive install --cask hammerspoon install --cask logi-options+ install --cask logitune install --cask docker-desktop install --cask raycast install --cask rectangle install --cask visual-studio-code install --cask google-chrome install --cask claude install --cask chatgpt' ]]
calls=()

# Personal Brewfile entries stay out of the professional profile.
install_optional_brewfile "$repo_root/dependencies/brew/personal/cli.Brewfile"
[[ "${calls[*]}" == 'install --cask xdevplatform/tap/xurl install langchain-ai/tap/langsmith-cli install openai/tools/tunnel-client' ]]
calls=()
install_optional_brewfile "$repo_root/dependencies/brew/personal/gui.Brewfile"
[[ "${calls[*]}" == 'install --cask bitwarden install --cask telegram install --cask whatsapp install --cask todoist-app install --cask notion' ]]
calls=()

# Both npm inventories install the same globally available CLIs as before.
install_npm_manifest "$repo_root/dependencies/npm/common.txt"
[[ "${calls[*]}" == 'npm install --global skills npm install --global agent-browser' ]]
calls=()
install_npm_manifest "$repo_root/dependencies/npm/personal.txt"
[[ "${calls[*]}" == 'npm install --global @wonderwhy-er/desktop-commander' ]]
calls=()

# Version checks still fail, including for an already installed CLI.
SKILLS_VERSION_FAIL=1
if install_npm_cli skills skills version 2>/dev/null; then exit 1; fi
unset SKILLS_VERSION_FAIL
BROWSER_VERSION_FAIL=1
if install_npm_cli agent-browser agent-browser version 2>/dev/null; then exit 1; fi
unset BROWSER_VERSION_FAIL
NPM_FAIL=1
if install_npm_cli skills skills version 2>/dev/null; then exit 1; fi
unset NPM_FAIL

# The personal-only Desktop Commander link points to the same globally installed binary.
configure_desktop_commander_cli
[[ "$(readlink "$HOME/.local/bin/desktop-commander-remote")" == "$test_dir/npm-prefix/bin/desktop-commander" ]]

# A malformed manifest fails explicitly instead of silently omitting a package.
printf 'invalid row\n' > "$test_dir/invalid.Brewfile"
if install_optional_brewfile "$test_dir/invalid.Brewfile" 2>/dev/null; then exit 1; fi
printf 'tool package unexpected extra\n' > "$test_dir/invalid-npm.txt"
if install_npm_manifest "$test_dir/invalid-npm.txt" 2>/dev/null; then exit 1; fi

# Profile membership and npm post-install hooks come from inventories, not code.
relocated="$test_dir/relocated"
mkdir -p "$relocated/dependencies/brew/personal" "$relocated/dependencies/npm"
printf 'cask "relocated-app" # apps: Relocated.app\n' > "$relocated/dependencies/brew/personal/gui.Brewfile"
printf 'desktop-commander @wonderwhy-er/desktop-commander none desktop-commander-link\n' > "$relocated/dependencies/npm/common.txt"
DOTFILES_ROOT="$relocated"
calls=()
install_optional_dependencies professional
[[ ${#calls[@]} -eq 0 ]]
install_optional_dependencies personal
[[ "${calls[*]}" == 'install --cask relocated-app' ]]
calls=()
rm "$HOME/.local/bin/desktop-commander-remote"
install_optional_dependencies common
[[ "${calls[*]}" == 'npm install --global @wonderwhy-er/desktop-commander' ]]
[[ "$(readlink "$HOME/.local/bin/desktop-commander-remote")" == "$test_dir/npm-prefix/bin/desktop-commander" ]]
DOTFILES_ROOT="$repo_root"
calls=()

# A fully provisioned Mac never reinstalls a cask, formula, or npm CLI,
# including after multiple applies and when GUI apps were installed manually.
calls=()
app_exists() { return 0; }
brew() {
  if [[ "$1" == list ]]; then return 1; fi
  calls+=("$*")
  return 99
}
command() {
  if [[ "$1" == -v ]]; then
    [[ "$2" == desktop-commander ]] && printf '%s\n' "$test_dir/npm-prefix/bin/desktop-commander"
    return 0
  fi
  builtin command "$@"
}
for iteration in 1 2; do
  install_optional_dependencies common >/dev/null
  install_optional_dependencies personal >/dev/null
  [[ ${#calls[@]} -eq 0 ]]
done

echo 'app installer: four Brewfile quadrants, two npm inventories, skip checks and failures passed (all installers stubbed)'
