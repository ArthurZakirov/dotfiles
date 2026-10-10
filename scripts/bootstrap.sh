#!/bin/bash
set -euo pipefail

load_bootstrap_module() {
  local entrypoint_dir module_path remote_ref temporary_module
  entrypoint_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  module_path="$entrypoint_dir/../src/bootstrap.sh"
  if [[ -r "$module_path" ]]; then
    source "$module_path"
    return
  fi

  [[ -n "${GITHUB_USERNAME:-}" ]] || {
    echo "Set GITHUB_USERNAME before running the remote bootstrap entry point." >&2
    exit 2
  }
  remote_ref="${DOTFILES_BRANCH:-HEAD}"
  temporary_module="$(mktemp)"
  curl -fsSL "https://raw.githubusercontent.com/${GITHUB_USERNAME}/dotfiles/${remote_ref}/src/bootstrap.sh" -o "$temporary_module"
  source "$temporary_module"
  rm -f "$temporary_module"
}

load_bootstrap_module
main "$@"
