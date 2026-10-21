#!/bin/bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../support/fresh_home_fixture.sh"

test_fresh_mac_rendering() {
  # GIVEN an ephemeral CI runner, the selected profile and a clean HOME
  require_ephemeral_runner
  given_ci_profile
  given_isolated_home

  # WHEN chezmoi initializes and applies the managed files without executing hooks
  when_chezmoi_renders_machine

  # THEN shared tools/configuration and profile-specific integrations work
  then_shared_setup_is_rendered
  then_profile_specific_setup_is_rendered
}

main() {
  test_fresh_mac_rendering
  echo "Fresh-home render/apply passed for $profile inside isolated CI HOME."
}

main "$@"
