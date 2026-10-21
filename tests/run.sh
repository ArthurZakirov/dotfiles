#!/bin/bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

run_shell_syntax_checks() {
  local script
  while IFS= read -r -d '' script; do
    bash -n "$script"
  done < <(
    find "$repo_root/home" "$repo_root/src" "$repo_root/tests" \
      -type f -name '*.sh' -print0
  )
}

run_unit_tests() {
  bash "$repo_root/tests/unit/test_shell_setup_module.sh"
  bash "$repo_root/tests/unit/test_apps.sh"
  bash "$repo_root/tests/unit/test_agent_browser_runtime.sh"
  bash "$repo_root/tests/unit/test_agent_skills.sh"
  PYTHONDONTWRITEBYTECODE=1 "$repo_root/.venv/bin/pytest" -q "$repo_root/tests/unit/test_pysetup.py" "$repo_root/tests/unit/test_local_skills_mcp.py" "$repo_root/tests/unit/test_dotfiles_secrets.py" "$repo_root/tests/unit/test_feature_documentation.py" "$repo_root/tests/unit/test_macos_shortcuts.py" "$repo_root/tests/unit/test_provisioning_log_grouping.py"
  bash "$repo_root/tests/integration/test_vscode_cli.sh"
}

run_integration_tests() {
  # Real chezmoi rendering and shell startup, without provisioning this Mac.
  PYTHONDONTWRITEBYTECODE=1 "$repo_root/.venv/bin/pytest" -q "$repo_root/tests/integration"
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
