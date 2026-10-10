#!/bin/bash
# Actual end-to-end provisioning. Must run only on an ephemeral macOS CI runner.
fixture_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$fixture_root/tests/support/assertions.sh"

require_ephemeral_runner() {
  [[ "${GITHUB_ACTIONS:-}" == true && -n "${RUNNER_TEMP:-}" ]] || {
    fail "Fresh-home provisioning is permitted only on an ephemeral GitHub Actions runner."
  }
}

given_ci_profile() {
  profile="${DOTFILES_PROFILE:?Set DOTFILES_PROFILE to personal or professional}"
  case "$profile" in
    personal|professional) ;;
    *) fail "Unsupported profile: $profile" ;;
  esac
}

given_isolated_home() {
  sandbox="$(mktemp -d "$RUNNER_TEMP/dotfiles-fresh-home.XXXXXX")"
  trap 'rm -rf "$sandbox"' EXIT

  export HOME="$sandbox/home"
  export GITHUB_USERNAME="${GITHUB_REPOSITORY_OWNER:-ArthurZakirov}"
  mkdir -p "$HOME"
  source_dir="$sandbox/source"
  config="$HOME/.config/chezmoi/chezmoi.toml"
}

when_chezmoi_provisions_machine() {
  local args=(
    --source "$source_dir" --destination "$HOME" --config "$config"
    init --apply
    --promptChoice "Mac profile=$profile"
    --promptString "GitHub username=$GITHUB_USERNAME"
  )
  if [[ "$profile" == personal ]]; then
    args+=(--promptString "Bitwarden Keychain account=bws-macbook-air")
  fi

  # Push tests exercise native GitHub username discovery; PR tests use the
  # checked-out revision so contributions from forks can also be validated.
  if [[ "${GITHUB_EVENT_NAME:-}" == push ]]; then
    args+=(--branch "$GITHUB_REF_NAME" "$GITHUB_USERNAME")
  else
    git clone --local "$fixture_root" "$source_dir"
  fi
  chezmoi "${args[@]}"
}

then_shared_setup_is_installed() {
  assert_file_exists "$HOME/.zshrc"
  assert_file_exists "$config"
  assert_directory_exists "$HOME/.oh-my-zsh"
  /bin/zsh -n "$HOME/.zshrc"
  assert_file_contains "$config" "profile = \"$profile\""
  assert_file_contains "$config" 'command = "code"'
}

then_profile_specific_setup_is_installed() {
  case "$profile" in
    personal)
      assert_file_contains "$HOME/.zshrc" 'LANGSMITH_TRACING=true'
      assert_file_contains "$HOME/.zshrc" 'bws()'
      export PATH="$HOME/.local/bin:$PATH"
      command -v bws >/dev/null || fail "Bitwarden CLI missing after personal setup"
      ;;
    professional)
      assert_file_excludes "$HOME/.zshrc" 'LANGSMITH_TRACING=true'
      assert_file_excludes "$HOME/.zshrc" 'bws()'
      ;;
  esac
}
