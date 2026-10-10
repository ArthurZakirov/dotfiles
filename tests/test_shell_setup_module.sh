#!/bin/bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export DOTFILES_ROOT="$repo_root"
export DOTFILES_PROFILE=professional
source "$repo_root/src/shell-setup.sh"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_calls() {
  local expected="$1"
  local actual="${calls[*]-}"
  [[ "$actual" == "$expected" ]] || fail "expected '$expected', got '$actual'"
}

# Exercise the actual editor and profile orchestration functions. Stub only
# concrete installers so tests cannot change the developer's environment.
calls=()
install_homebrew() { calls+=(homebrew); }
configure_homebrew() { calls+=(configure); }
install_homebrew_packages() { calls+=(packages); }
install_visual_studio_code() { calls+=(vscode); }
install_oh_my_zsh() { calls+=(oh-my-zsh); }
install_bitwarden_secrets_manager() { calls+=(bitwarden); }

DOTFILES_PROFILE=professional
main
assert_calls "homebrew configure packages vscode oh-my-zsh"

calls=()
DOTFILES_PROFILE=personal
main
assert_calls "homebrew configure packages vscode oh-my-zsh bitwarden"

# Invalid profiles must be rejected before any provisioning side effects.
calls=()
DOTFILES_PROFILE=unknown
if output="$(main 2>&1)"; then
  fail "unsupported profile unexpectedly succeeded"
fi
[[ "$output" == *"Unsupported Mac profile: unknown"* ]] || fail "missing profile validation error"
assert_calls ""

echo "shell setup module: editors and profile dispatch verified without side effects"
