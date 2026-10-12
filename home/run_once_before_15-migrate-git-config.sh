#!/bin/sh
# Preserve an existing global Git configuration as this machine's local override.
set -eu

global_config="$HOME/.gitconfig"
local_config="$HOME/.gitconfig.local"

if [ -f "$global_config" ] && [ ! -e "$local_config" ]; then
  mv "$global_config" "$local_config"
elif [ -f "$global_config" ] && [ -e "$local_config" ]; then
  echo "Both $global_config and $local_config exist; merge them before applying dotfiles." >&2
  exit 1
elif [ ! -e "$local_config" ]; then
  : > "$local_config"
fi
