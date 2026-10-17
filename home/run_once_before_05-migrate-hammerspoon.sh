#!/bin/bash
set -euo pipefail

# Take over the managed Hammerspoon paths without assuming anything about the
# previous setup. Preserve the complete original tree and dereference replaced
# symlinks before changing any of them.
root="$HOME/.hammerspoon"
marker="$HOME/.cache/chezmoi/hammerspoon-migration-complete"
[[ -f "$marker" ]] && exit 0

# A missing installation needs no migration. A dangling root symlink is not a
# fresh installation: refuse to overwrite it until the user resolves it.
[[ -e "$root" || -L "$root" ]] || exit 0
if [[ ! -d "$root" ]]; then
  printf 'Cannot migrate Hammerspoon: %s is not an accessible directory.\n' "$root" >&2
  exit 1
fi

backup_parent="$HOME/Library/Application Support/dotfiles/backups"
mkdir -p "$backup_parent"
backup_parent_real="$(cd "$backup_parent" && pwd -P)"

# Do not recursively copy an ancestor of the backup directory into itself.
# A misconfigured symlink might otherwise snapshot all of HOME (or /).
contains_backup_dir() {
  [[ -d "$1" ]] || return 1
  local target_real
  target_real="$(cd "$1" && pwd -P)"
  [[ "$target_real" == / || "$backup_parent_real/" == "$target_real/"* ]]
}
for candidate in "$root" "$root/init.lua" "$root/modules" "$root/bin" "$HOME/.hammerspoon-local"; do
  if contains_backup_dir "$candidate"; then
    printf 'Cannot safely back up Hammerspoon: %s contains the backup directory.\n' "$candidate" >&2
    exit 1
  fi
done
backup="$(mktemp -d "$backup_parent/hammerspoon-$(date +%Y%m%d-%H%M%S)-XXXXXXXX")"

# -H follows only a symlink provided as the command-line argument, leaving
# links within the tree intact. The snapshot is independent of the root target.
cp -RH "$root" "$backup/hammerspoon"
if [[ -L "$root" ]]; then
  cp -P "$root" "$backup/original-root-link"
fi
if [[ -d "$HOME/.hammerspoon-local" ]]; then
  cp -RH "$HOME/.hammerspoon-local" "$backup/hammerspoon-local"
fi

# The tree snapshot retains links, while this separate copy also preserves
# their contents in case the old source directory is later moved or deleted.
mkdir "$backup/resolved"
for entry in init.lua modules bin; do
  if [[ -L "$root/$entry" && -e "$root/$entry" ]]; then
    cp -RH "$root/$entry" "$backup/resolved/$entry"
  fi
done

# Never apply through a symlinked ~/.hammerspoon directory; that would modify
# the old external checkout. Materialize a real directory from the snapshot.
if [[ -L "$root" ]]; then
  cp -RP "$backup/hammerspoon" "$backup/new-root"
  unlink "$root"
  mv "$backup/new-root" "$root"
fi

# Chezmoi owns these three paths. It must not follow a pre-existing symlink
# into arbitrary external locations. Ordinary files and directories are left
# for chezmoi to update; unrelated contents (e.g. Spoons/) are not touched.
for entry in init.lua modules bin; do
  if [[ -L "$root/$entry" ]]; then
    unlink "$root/$entry"
  fi
done

mkdir -p "$(dirname "$marker")"
touch "$marker"
printf 'Saved existing Hammerspoon configuration to %s\n' "$backup"
