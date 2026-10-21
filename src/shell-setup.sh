#!/bin/bash

: "${DOTFILES_ROOT:?DOTFILES_ROOT must point to the dotfiles checkout}"
: "${DOTFILES_PROFILE:?DOTFILES_PROFILE must be personal or professional}"
module_dir="${DOTFILES_MODULE_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
source "$module_dir/homebrew.sh"
source "$module_dir/apps.sh"
source "$module_dir/setup-actions.sh"

install_homebrew_packages() {
  export PATH="$HOME/.local/bin:$PATH"
  brew bundle install --no-upgrade --file="$DOTFILES_ROOT/dependencies/brew/required.Brewfile"
}

install_profile_dependencies() {
  local scope="$1"
  # Required manual installations retain the original CI behavior.
  install_manual_dependencies "$scope" || return
  if [[ "${DOTFILES_SKIP_OPTIONAL_APPS:-}" != 1 ]]; then
    install_optional_dependencies "$scope" || return
    run_pending_brew_actions || return
  fi
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
  install_homebrew
  configure_homebrew
  install_homebrew_packages
  # GitHub's ephemeral runners test rendering and shell provisioning, not GUI
  # downloads. Regular Macs always execute the full application setup.
  if [[ "${DOTFILES_SKIP_OPTIONAL_APPS:-}" != 1 ]]; then
    install_optional_dependencies common
    verify_node_toolchain
    run_pending_brew_actions
  fi
  install_git_dependencies common || return
  install_git_dependencies "$DOTFILES_PROFILE" || return
  install_manual_dependencies common || return
  install_profile_dependencies "$DOTFILES_PROFILE"
}
