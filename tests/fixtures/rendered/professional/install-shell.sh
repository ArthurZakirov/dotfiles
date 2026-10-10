#!/bin/bash
set -euo pipefail

DOTFILES_ROOT="<DOTFILES_REPO>"
DOTFILES_PROFILE="professional"
source "$DOTFILES_ROOT/src/shell-setup.sh"
main "$@"
