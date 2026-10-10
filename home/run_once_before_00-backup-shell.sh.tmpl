#!/bin/bash
set -euo pipefail

# On initial provisioning, preserve an existing zshrc before chezmoi applies it.
# The once_ attribute avoids making backups on every chezmoi update.
if [[ -f "$HOME/.zshrc" ]]; then
  backup_dir="$HOME/Library/Application Support/dotfiles/backups/$(date +%Y%m%d-%H%M%S)-$$"
  mkdir -p "$backup_dir"
  cp -p "$HOME/.zshrc" "$backup_dir/zshrc"
  echo "Existing .zshrc backed up to: $backup_dir"
fi
