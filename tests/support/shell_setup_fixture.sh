#!/bin/bash
# Replaces concrete installers with in-memory spies.
# Tests exercise the real orchestration and never install anything.
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
export DOTFILES_ROOT="$repo_root"
export DOTFILES_PROFILE=professional
source "$repo_root/src/shell-setup.sh"
source "$repo_root/tests/support/assertions.sh"

record_installation() {
  installed_tools+=("$1")
}

install_homebrew() { record_installation homebrew; }
configure_homebrew() { record_installation configure; }
install_homebrew_packages() { record_installation packages; }
install_visual_studio_code() { record_installation vscode; }
install_common_apps() { record_installation apps; }
install_oh_my_zsh() { record_installation oh-my-zsh; }
install_bitwarden_secrets_manager() { record_installation bitwarden; }

given_profile() {
  DOTFILES_PROFILE="$1"
  installed_tools=()
}

assert_installation_sequence() {
  local actual="${installed_tools[*]-}"
  [[ "$actual" == "$1" ]] || fail "expected installations '$1', got '$actual'"
}
