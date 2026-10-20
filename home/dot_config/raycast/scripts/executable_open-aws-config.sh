#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title Open AWS config
# @raycast.mode silent
# @raycast.packageName Configuration Files
# @raycast.description Open the local AWS profiles file in VS Code

set -euo pipefail

target="$HOME/.aws/config"
if [[ ! -f "$target" ]]; then
  printf 'File not found: %s\n' "$target" >&2
  exit 1
fi

open -a "Visual Studio Code" "$target"
