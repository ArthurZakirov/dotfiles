#!/bin/sh
# Consistent, plain-text section headings for chezmoi lifecycle hooks.
dotfiles_section() {
  printf '\n'
  printf '============================================================\n'
  printf '  %s\n' "$1"
  printf '============================================================\n\n'
}
