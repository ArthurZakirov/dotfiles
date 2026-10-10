#!/bin/bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export DOTFILES_ROOT="$repo_root"
export DOTFILES_PROFILE=professional
source "$repo_root/src/shell-setup.sh"

# Verify provisioning is orchestrated in the required order without installing
# or modifying anything on the developer's Mac.
calls=()
install_homebrew() { calls+=(homebrew); }
configure_homebrew() { calls+=(configure); }
install_homebrew_packages() { calls+=(packages); }
install_editor() { calls+=(editor); }
install_oh_my_zsh() { calls+=(oh-my-zsh); }
install_profile_tools() { calls+=(profile); }

main
actual="${calls[*]}"
expected="homebrew configure packages editor oh-my-zsh profile"
[[ "$actual" == "$expected" ]] || {
  echo "Unexpected provisioning sequence: $actual" >&2
  exit 1
}
echo "shell setup module: provisioning order verified without side effects"
