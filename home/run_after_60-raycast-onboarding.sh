#!/bin/sh
# Raycast Store installation is interactive; open the official listing once
# on each Mac without touching Raycast's local databases or private history.
set -eu

if [ "$(uname -s)" != Darwin ]; then
  exit 0
fi

if [ ! -d /Applications/Raycast.app ] && [ ! -d "$HOME/Applications/Raycast.app" ]; then
  echo 'Raycast not installed; skipping Repository Manager onboarding.' >&2
  exit 0
fi

printf "\n  -- RAYCAST --\n"
marker="$HOME/.cache/chezmoi/raycast-repository-manager-store-opened"
if [ -e "$marker" ]; then
  echo "Raycast: Repository Manager onboarding already offered."
  exit 0
fi

# Raycast has no supported CLI for querying or silently installing Store extensions.
# An already-installed extension may show its Store page once; this is harmless.
open 'https://www.raycast.com/francesco_mecchi/repository-manager'
mkdir -p "$(dirname "$marker")"
: > "$marker"
printf '%s\n' 'Raycast: confirm Repository Manager installation in the Store.' \
  'Raycast: add ~/.config/raycast/scripts under Settings -> Script Commands.' \
  'Raycast: assign Option+R to the repository list command (once per Mac).'
