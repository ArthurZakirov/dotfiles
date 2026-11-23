#!/bin/bash
# Real isolated chezmoi rendering/apply (without running installation or service hooks).
fixture_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$fixture_root/tests/support/assertions.sh"

require_ephemeral_runner() {
  [[ "${GITHUB_ACTIONS:-}" == true && -n "${RUNNER_TEMP:-}" ]] || {
    fail "Fresh-home rendering is permitted only on an ephemeral GitHub Actions runner."
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

when_chezmoi_renders_machine() {
  local args=(
    --source "$source_dir" --destination "$HOME" --config "$config"
    init
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
  # Existing Herdr preferences and unrelated shortcuts survive the first apply.
  mkdir -p "$HOME/.config/herdr-app"
  printf '%s\n' '{"zoom":1.5,"custom_setting":true}' > "$HOME/.config/herdr-app/settings.json"
  printf '%s\n' '{"global":{"cmd-t":"custom.tab","cmd-k":"old.action"},"custom":{"f1":"help"}}' > "$HOME/.config/herdr-app/keys.json"
  chezmoi "${args[@]}"
  chezmoi --source "$source_dir" --destination "$HOME" --config "$config" \
    apply --exclude scripts --force
}

then_shared_setup_is_rendered() {
  python3 - "$HOME/.config/herdr-app" <<'PYTHON'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
settings = json.loads((root / "settings.json").read_text())
keys = json.loads((root / "keys.json").read_text())
assert settings["zoom"] == 1.5 and settings["custom_setting"]
assert settings["appearance"] == "dark"
assert keys["custom"]["f1"] == "help" and keys["global"]["cmd-t"] == "custom.tab"
assert keys["global"]["cmd-k"] == "codex-history-launcher.open"
PYTHON
  assert_file_contains "$HOME/.config/herdr-app/keys.json" "$HOME/.local/bin/codex-voice"
  assert_file_contains "$HOME/.config/herdr-app/mods/codex-history-launcher/main.js" "$HOME/.local/bin/herdr-codex-history"
  assert_file_contains "$HOME/.config/herdr-app/shared.json" 'main-with-history'
  assert_file_exists "$HOME/.config/herdr-app/layouts/main-with-history.json"
  assert_file_contains "$HOME/.local/bin/herdr-codex-history" "#!$HOME/.local/share/herdr-history-venv/bin/python"
  assert_file_exists "$HOME/.zshrc"
  assert_file_exists "$config"
  /bin/zsh -n "$HOME/.zshrc"
  assert_file_contains "$config" "profile = \"$profile\""
  assert_file_contains "$config" 'command = "code"'
}

then_profile_specific_setup_is_rendered() {
  case "$profile" in
    personal)
      assert_file_contains "$HOME/.zshrc" 'LANGSMITH_TRACING=true'
      assert_file_contains "$HOME/.zshrc" 'bws()'
      ;;
    professional)
      assert_file_excludes "$HOME/.zshrc" 'LANGSMITH_TRACING=true'
      assert_file_excludes "$HOME/.zshrc" 'bws()'
      ;;
  esac
}
