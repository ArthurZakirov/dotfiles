#!/bin/bash
# Open an existing Raycast navigation target in VS Code.
# Kept outside scripts/ so Raycast only indexes the named command wrappers.
set -euo pipefail

# Raycast does not necessarily inherit an interactive shell's Homebrew PATH.
PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"

kind="${1:-}"
case "$kind" in
  file|directory)
    if [[ $# -ne 2 ]]; then
      printf 'Usage: %s {file|directory} TARGET\n' "$0" >&2
      exit 2
    fi
    target="$2"
    ;;
  chezmoi-repo)
    if [[ $# -ne 1 ]]; then
      printf 'Usage: %s chezmoi-repo\n' "$0" >&2
      exit 2
    fi
    target="$(git -C "$(chezmoi source-path)" rev-parse --show-toplevel)"
    ;;
  *)
    printf 'Unknown target type: %s\n' "$kind" >&2
    exit 2
    ;;
esac

if [[ "$kind" == file ]]; then
  if [[ ! -f "$target" ]]; then
    printf 'File not found: %s\n' "$target" >&2
    exit 1
  fi
elif [[ ! -d "$target" ]]; then
  printf 'Directory not found: %s\n' "$target" >&2
  exit 1
fi

open -a "Visual Studio Code" "$target"
