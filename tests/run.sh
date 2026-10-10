#!/bin/bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

run_shell_syntax_checks() {
  local script
  for script in \
    "$repo_root/src/homebrew.sh" \
    "$repo_root/src/shell-setup.sh" \
    "$repo_root/tests/unit/test_shell_setup_module.sh" \
    "$repo_root/tests/support/shell_setup_fixture.sh" \
    "$repo_root/tests/integration/run_fresh_home.sh" \
    "$repo_root/tests/support/fresh_home_fixture.sh" \
    "$repo_root/tests/support/assertions.sh"; do
    bash -n "$script"
  done
}

run_unit_tests() {
  bash "$repo_root/tests/unit/test_shell_setup_module.sh"
}

run_integration_tests() {
  # Real chezmoi rendering and shell startup, without provisioning this Mac.
  PYTHONDONTWRITEBYTECODE=1 "$repo_root/.venv/bin/pytest" -q "$repo_root/tests/integration/test_profiles.py"
}

run_quality_checks() {
  git -C "$repo_root" diff --check
}

main() {
  run_shell_syntax_checks
  run_unit_tests
  run_integration_tests
  run_quality_checks
}

main "$@"
