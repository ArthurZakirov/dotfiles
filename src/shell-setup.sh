#!/bin/bash

: "${DOTFILES_ROOT:?DOTFILES_ROOT must point to the dotfiles checkout}"
: "${DOTFILES_PROFILE:?DOTFILES_PROFILE must be personal or professional}"
module_dir="${DOTFILES_MODULE_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
source "$module_dir/homebrew.sh"
source "$module_dir/apps.sh"
source "$module_dir/setup-actions.sh"
source "$module_dir/provisioning-log.sh"

install_profile_dependencies() {
  local scope="$1"
  dotfiles_subsection "APPLICATIONS AND CLI / $scope"
  install_manifest_dependencies "$scope" || return
  run_pending_brew_actions || return
  install_manual_dependencies "$scope" || return
}

main() {
  [[ "$(uname -s)" == Darwin ]] || {
    echo "This dotfiles setup currently requires macOS." >&2
    return 1
  }
  case "$DOTFILES_PROFILE" in
    personal|professional) ;;
    *) echo "Unsupported Mac profile: $DOTFILES_PROFILE" >&2; return 2 ;;
  esac
  dotfiles_section "01 / DEPENDENCIES"
  install_homebrew || return
  configure_homebrew || return
  export PATH="$HOME/.local/bin:$PATH"
  install_profile_dependencies common || return
  verify_node_toolchain || return
  dotfiles_subsection "SHELL FRAMEWORK AND GIT"
  install_git_dependencies common || return
  install_git_dependencies "$DOTFILES_PROFILE" || return
  install_profile_dependencies "$DOTFILES_PROFILE"
}
