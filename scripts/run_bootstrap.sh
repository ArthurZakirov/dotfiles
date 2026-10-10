#!/bin/bash
set -euo pipefail

load_bootstrap_module() {
  local entrypoint_dir module_path module_dir remote_ref temporary_module_dir
  entrypoint_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  module_dir="$entrypoint_dir/../src"
  module_path="$module_dir/bootstrap.sh"
  if [[ -r "$module_path" ]]; then
    export DOTFILES_MODULE_DIR="$module_dir"
    source "$module_path"
    return
  fi

  [[ -n "${GITHUB_USERNAME:-}" ]] || {
    echo "Set GITHUB_USERNAME before running the remote bootstrap entry point." >&2
    exit 2
  }
  remote_ref="${DOTFILES_BRANCH:-HEAD}"
  temporary_module_dir="$(mktemp -d)"
  curl -fsSL "https://raw.githubusercontent.com/${GITHUB_USERNAME}/dotfiles/${remote_ref}/src/bootstrap.sh" -o "$temporary_module_dir/bootstrap.sh"
  curl -fsSL "https://raw.githubusercontent.com/${GITHUB_USERNAME}/dotfiles/${remote_ref}/src/homebrew.sh" -o "$temporary_module_dir/homebrew.sh"
  export DOTFILES_MODULE_DIR="$temporary_module_dir"
  source "$DOTFILES_MODULE_DIR/bootstrap.sh"
  rm -rf "$temporary_module_dir"
}

load_bootstrap_module
main "$@"
