#!/bin/bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

run_shell_syntax_checks() {
  bash -n "$repo_root/src/homebrew.sh" "$repo_root/src/shell-setup.sh"
  bash -n "$repo_root/tests/test_shell_setup_module.sh" "$repo_root/tests/support/shell_setup_fixture.sh"
  bash -n "$repo_root/tests/run_fresh_home.sh" "$repo_root/tests/support/fresh_home_fixture.sh" "$repo_root/tests/support/assertions.sh"
}

run_unit_tests() {
  bash "$repo_root/tests/test_shell_setup_module.sh"
  python3 -B "$repo_root/scripts/verify.py"
}

run_quality_checks() {
  git -C "$repo_root" diff --check
}

main() {
  run_shell_syntax_checks
  run_unit_tests
  run_quality_checks
}

main "$@"
