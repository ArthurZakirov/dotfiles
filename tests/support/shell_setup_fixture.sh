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
run_pending_brew_actions() {
  if [[ "${last_installed_scope:-}" == common ]]; then record_installation vscode-cli; fi
  return 0
}
install_manifest_dependencies() {
  last_installed_scope="$1"
  case "$1" in
    common) record_installation apps ;;
    personal) record_installation personal-apps ;;
    professional) : ;;
  esac
}
verify_node_toolchain() { record_installation node-tools; }
install_git_dependencies() {
  if [[ "$1" == common ]]; then record_installation oh-my-zsh; fi
  return 0
}
install_manual_dependencies() {
  if [[ "$1" == personal ]]; then record_installation bitwarden; fi
  return 0
}
install_bitwarden_secrets_manager() { record_installation bitwarden; }

given_profile() {
  DOTFILES_PROFILE="$1"
  installed_tools=()
}

assert_installation_sequence() {
  local actual="${installed_tools[*]-}"
  [[ "$actual" == "$1" ]] || fail "expected installations '$1', got '$actual'"
}
