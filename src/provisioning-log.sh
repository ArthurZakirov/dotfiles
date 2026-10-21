#!/bin/sh
# Consistent, plain-text section headings for chezmoi lifecycle hooks.
dotfiles_section() {
  printf '\n'
  printf '============================================================\n'
  printf '  %s\n' "$1"
  printf '============================================================\n\n'
}

# Nested headings are intentionally less prominent than lifecycle phases.
dotfiles_subsection() {
  printf "\n  -- %s --\n" "$1"
}
