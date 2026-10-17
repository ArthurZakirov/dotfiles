#!/bin/bash
set -euo pipefail

# Replace only the symlinks installed by the previous Hammerspoon configuration.
# Back up the existing live configuration before changing any links.
root="$HOME/.hammerspoon"
marker="$HOME/.cache/chezmoi/hammerspoon-migration-complete"
[[ -f "$marker" ]] && exit 0
[[ -d "$root" ]] || exit 0

for entry in init.lua modules bin; do
  [[ -L "$root/$entry" ]] || continue
  link_target="$(readlink "$root/$entry")"
  case "$entry:$link_target" in
    "init.lua:$HOME/.hammerspoon-local/init.lua" | \
    "init.lua:$HOME/.agents/skills/hammerspoon-macos-setup/assets/hammerspoon/init.lua" | \
    "modules:$HOME/.agents/skills/hammerspoon-macos-setup/assets/hammerspoon/modules" | \
    "bin:$HOME/.agents/skills/hammerspoon-macos-setup/assets/hammerspoon/bin") ;;
    *)
      printf 'Refusing to replace an unknown Hammerspoon symlink: %s -> %s\n' "$root/$entry" "$link_target" >&2
      exit 1
      ;;
  esac
done

# A fresh Mac has nothing to preserve. Existing Spoons and other files stay put.
if [[ -n "$(ls -A "$root")" ]]; then
  backup="$HOME/Library/Application Support/dotfiles/backups/$(date +%Y%m%d-%H%M%S)-$$"
  mkdir -p "$backup"
  cp -RP "$root" "$backup/hammerspoon"
  if [[ -d "$HOME/.hammerspoon-local" ]]; then
    cp -RP "$HOME/.hammerspoon-local" "$backup/hammerspoon-local"
  fi
  # Symlink targets may disappear later; also preserve their current contents.
  mkdir "$backup/resolved"
  for entry in init.lua modules bin; do
    if [[ -L "$root/$entry" && -e "$root/$entry" ]]; then
      cp -RL "$root/$entry" "$backup/resolved/$entry"
    fi
  done
  printf 'Saved existing Hammerspoon configuration to %s\n' "$backup"
fi

for entry in init.lua modules bin; do
  if [[ -L "$root/$entry" ]]; then
    unlink "$root/$entry"
  fi
done
mkdir -p "$(dirname "$marker")"
touch "$marker"
