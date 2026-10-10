#!/bin/bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/support/shell_setup_fixture.sh"

test_professional_profile_installs_shared_tools_only() {
  # GIVEN a professional Mac with stubbed concrete installers
  given_profile professional

  # WHEN shell setup runs
  main

  # THEN the common installers run, without Bitwarden
  assert_installation_sequence "homebrew configure packages vscode oh-my-zsh"
}

test_personal_profile_installs_bitwarden_after_shared_tools() {
  # GIVEN a personal Mac with stubbed concrete installers
  given_profile personal

  # WHEN shell setup runs
  main

  # THEN its profile factory adds the Bitwarden installer
  assert_installation_sequence "homebrew configure packages vscode oh-my-zsh bitwarden"
}

test_editor_factory_calls_visual_studio_code_installer() {
  # GIVEN a profile with concrete installer spies
  given_profile professional

  # WHEN installing all configured editors
  install_editors

  # THEN the VS Code installer is invoked exactly once
  assert_installation_sequence "vscode"
}

test_personal_factory_calls_bitwarden_installer() {
  # GIVEN the personal-profile installer
  given_profile personal

  # WHEN its profile-specific tools are installed
  install_personal_profile

  # THEN only Bitwarden Secrets Manager is requested
  assert_installation_sequence "bitwarden"
}

test_professional_factory_has_no_additional_tools() {
  # GIVEN the professional-profile installer
  given_profile professional

  # WHEN its profile-specific tools are installed
  install_professional_profile

  # THEN no personal-only tools are requested
  assert_installation_sequence ""
}

test_invalid_profile_fails_before_installing_anything() {
  # GIVEN an unsupported profile
  given_profile unknown

  # WHEN shell setup is invoked
  local error
  if error="$(main 2>&1)"; then
    fail "unsupported profile unexpectedly succeeded"
  fi

  # THEN the error is actionable and no installers ran
  assert_contains "$error" "Unsupported Mac profile: unknown"
  assert_installation_sequence ""
}

main_tests() {
  test_professional_profile_installs_shared_tools_only
  test_personal_profile_installs_bitwarden_after_shared_tools
  test_editor_factory_calls_visual_studio_code_installer
  test_personal_factory_calls_bitwarden_installer
  test_professional_factory_has_no_additional_tools
  test_invalid_profile_fails_before_installing_anything
  echo "shell setup: 6 Given/When/Then cases passed (no installers executed)"
}

main_tests
