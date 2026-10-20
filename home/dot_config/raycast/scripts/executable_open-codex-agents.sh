#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title Open Codex AGENTS.md
# @raycast.mode silent
# @raycast.packageName Configuration Files
# @raycast.description Open Codex agent instructions in VS Code

set -euo pipefail

target="$HOME/.codex/AGENTS.md"
if [[ ! -f "$target" ]]; then
  printf 'File not found: %s\n' "$target" >&2
  exit 1
fi

open -a "Visual Studio Code" "$target"
