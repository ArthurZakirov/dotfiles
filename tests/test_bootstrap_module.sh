#!/bin/bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/src/bootstrap.sh"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_equal() {
  [[ "$1" == "$2" ]] || fail "expected '$1', got '$2'"
}

parse_arguments professional
assert_equal professional "$profile"

export GITHUB_USERNAME=test-account
export DOTFILES_SOURCE_DIR=/tmp/test-dotfiles
export DOTFILES_BRANCH=test-branch
load_configuration
assert_equal test-account "$github_username"
assert_equal /tmp/test-dotfiles "$dotfiles_source_dir"
assert_equal test-branch "$dotfiles_branch"
unset GITHUB_USERNAME DOTFILES_SOURCE_DIR DOTFILES_BRANCH

if output="$(env -u GITHUB_USERNAME bash -c '
  source "$1"
  load_configuration
  validate_environment
' -- "$repo_root/src/bootstrap.sh" 2>&1)"; then
  fail "missing GitHub username unexpectedly passed validation"
fi
[[ "$output" == *"Set GITHUB_USERNAME"* ]] || fail "missing username error was not actionable"

echo "bootstrap module: configuration and validation passed"
