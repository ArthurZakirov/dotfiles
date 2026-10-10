#!/bin/bash
set -euo pipefail

# This integration test installs real packages. Never execute on a personal Mac.
[[ "${GITHUB_ACTIONS:-}" == true && -n "${RUNNER_TEMP:-}" ]] || {
  echo "Fresh-home provisioning is permitted only on an ephemeral GitHub Actions runner." >&2
  exit 2
}

profile="${DOTFILES_PROFILE:?Set DOTFILES_PROFILE to personal or professional}"
case "$profile" in
  personal|professional) ;;
  *) echo "Unsupported profile: $profile" >&2; exit 2 ;;
esac

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sandbox="$(mktemp -d "$RUNNER_TEMP/dotfiles-fresh-home.XXXXXX")"
trap 'rm -rf "$sandbox"' EXIT

export HOME="$sandbox/home"
export GITHUB_USERNAME="${GITHUB_REPOSITORY_OWNER:-ArthurZakirov}"
mkdir -p "$HOME"
source_dir="$sandbox/source"

# Verify chezmoi's native GitHub-username discovery on branch pushes. Pull
# requests instead use the checked-out commit (including fork contributions).
init_args=(--source "$source_dir" --destination "$HOME" --config "$HOME/.config/chezmoi/chezmoi.toml" init --apply
  --promptChoice "Mac profile=$profile"
  --promptString "GitHub username=$GITHUB_USERNAME")

if [[ "$profile" == personal ]]; then
  init_args+=(--promptString "Bitwarden Keychain account=bws-macbook-air")
fi

if [[ "${GITHUB_EVENT_NAME:-}" == push ]]; then
  init_args+=(--branch "$GITHUB_REF_NAME" "$GITHUB_USERNAME")
else
  git clone --local "$repo_root" "$source_dir"
fi

chezmoi "${init_args[@]}"

[[ -f "$HOME/.zshrc" ]]
[[ -d "$HOME/.oh-my-zsh" ]]
[[ -f "$HOME/.config/chezmoi/chezmoi.toml" ]]
/bin/zsh -n "$HOME/.zshrc"
grep -q "profile = \"$profile\"" "$HOME/.config/chezmoi/chezmoi.toml"
grep -q 'command = "code"' "$HOME/.config/chezmoi/chezmoi.toml"

if [[ "$profile" == personal ]]; then
  grep -q 'LANGSMITH_TRACING=true' "$HOME/.zshrc"
  grep -q 'bws()' "$HOME/.zshrc"
  export PATH="$HOME/.local/bin:$PATH"
  command -v bws >/dev/null || { echo "Bitwarden CLI missing after personal setup" >&2; exit 1; }
else
  ! grep -q 'LANGSMITH_TRACING=true' "$HOME/.zshrc"
  ! grep -q 'bws()' "$HOME/.zshrc"
fi

echo "Fresh-home provisioning passed for $profile inside isolated CI HOME."
