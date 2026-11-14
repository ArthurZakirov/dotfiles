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
  PYTHONDONTWRITEBYTECODE=1 "$repo_root/.venv/bin/pytest" -q "$repo_root/tests/unit/test_pysetup.py" "$repo_root/tests/unit/test_pr_navigation.py" "$repo_root/tests/unit/test_local_skills_mcp.py" "$repo_root/tests/unit/test_dotfiles_secrets.py" "$repo_root/tests/unit/test_feature_documentation.py" "$repo_root/tests/unit/test_macos_shortcuts.py" "$repo_root/tests/unit/test_provisioning_log_grouping.py" "$repo_root/tests/unit/test_dependency_architecture.py" "$repo_root/tests/unit/test_codex_agents_md_freshness.py" "$repo_root/tests/unit/test_codex_voice_install.py" "$repo_root/tests/unit/test_storage_maintenance.py" "$repo_root/tests/unit/test_session_find.py" "$repo_root/tests/unit/test_codex_text.py" "$repo_root/tests/unit/test_find_gpt_session.py" "$repo_root/tests/unit/test_session_open.py" "$repo_root/tests/unit/test_hammerspoon_gpt_sessions.py"
  bash "$repo_root/tests/integration/test_vscode_cli.sh"
}

run_integration_tests() {
  # Real chezmoi rendering and shell startup, without provisioning this Mac.
  PYTHONDONTWRITEBYTECODE=1 "$repo_root/.venv/bin/pytest" -q "$repo_root/tests/integration"
}

run_quality_checks() {
  git -C "$repo_root" diff --check
  # The native ChatGPT browser adapter uses AppKit/Accessibility. Compile its
  # type declarations on the existing macOS CI runner, not only the Python CLI.
  if [[ "$(uname -s)" == "Darwin" ]]; then
    local swift_source="$repo_root/home/dot_local/share/find-gpt-session/ui.swift"
    local swift_tmp
    swift_tmp="$(mktemp -d)"
    swiftc -typecheck "$swift_source"
    # Execute synthetic UI-result collision checks on a real macOS runner.
    # This does not require an authenticated browser or Accessibility access.
    swiftc "$swift_source" -o "$swift_tmp/ui-ax-self-test"
    "$swift_tmp/ui-ax-self-test" --self-test
    rm -rf -- "$swift_tmp"
  fi
}

main() {
  run_shell_syntax_checks
  run_unit_tests
  run_integration_tests
  run_quality_checks
}

main "$@"
