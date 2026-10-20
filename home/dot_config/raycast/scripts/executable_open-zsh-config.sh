#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title Open .zshrc
# @raycast.mode silent
# @raycast.packageName Configuration Files
# @raycast.description Open your Zsh configuration in VS Code

set -euo pipefail

target="$HOME/.zshrc"
if [[ ! -f "$target" ]]; then
  printf 'File not found: %s\n' "$target" >&2
  exit 1
fi

open -a "Visual Studio Code" "$target"
