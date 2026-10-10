#!/bin/bash
set -euo pipefail

DOTFILES_ROOT="<DOTFILES_REPO>"
DOTFILES_PROFILE="personal"
source "$DOTFILES_ROOT/src/shell-setup.sh"
main "$@"
