#!/bin/bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/support/fresh_home_fixture.sh"

test_fresh_mac_provisioning() {
  # GIVEN an ephemeral CI runner, the selected profile and a clean HOME
  require_ephemeral_runner
  given_ci_profile
  given_isolated_home

  # WHEN chezmoi initializes the source and applies its real installation hooks
  when_chezmoi_provisions_machine

  # THEN shared tools/configuration and profile-specific integrations work
  then_shared_setup_is_installed
  then_profile_specific_setup_is_installed
}

main() {
  test_fresh_mac_provisioning
  echo "Fresh-home provisioning passed for $profile inside isolated CI HOME."
}

main "$@"
