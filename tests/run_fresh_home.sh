#!/bin/bash
set -euo pipefail

# This integration test installs real packages. Never execute on a personal Mac.
[[ "${GITHUB_ACTIONS:-}" == true && -n "${RUNNER_TEMP:-}" ]] || {
  echo "Fresh-home provisioning is permitted only on an ephemeral GitHub Actions runner." >&2
  exit 2
}

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
  --promptChoice "Mac profile=professional"
  --promptString "GitHub username=$GITHUB_USERNAME")

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
grep -q 'profile = "professional"' "$HOME/.config/chezmoi/chezmoi.toml"
grep -q 'command = "code"' "$HOME/.config/chezmoi/chezmoi.toml"
echo "Fresh-home provisioning passed inside isolated CI HOME."
