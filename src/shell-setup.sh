#!/bin/bash

: "${DOTFILES_ROOT:?DOTFILES_ROOT must point to the dotfiles checkout}"
: "${DOTFILES_PROFILE:?DOTFILES_PROFILE must be personal or professional}"
module_dir="${DOTFILES_MODULE_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
source "$module_dir/homebrew.sh"

install_homebrew_packages() {
  export PATH="$HOME/.local/bin:$PATH"
  brew bundle install --no-upgrade --file="$DOTFILES_ROOT/Brewfile"
}

install_editor() {
  local app
  if [[ ! -d "/Applications/Visual Studio Code.app" && ! -d "$HOME/Applications/Visual Studio Code.app" ]]; then
    brew install --cask visual-studio-code
  fi
  if ! command -v code >/dev/null 2>&1; then
    app="/Applications/Visual Studio Code.app"
    [[ -d "$app" ]] || app="$HOME/Applications/Visual Studio Code.app"
    mkdir -p "$HOME/.local/bin"
    ln -s "$app/Contents/Resources/app/bin/code" "$HOME/.local/bin/code"
  fi
}

install_oh_my_zsh() {
  local omz="$HOME/.oh-my-zsh"
  local revision
  revision="$(sed -n 's/^ohMyZshCommit = "\(.*\)"/\1/p' "$DOTFILES_ROOT/home/.chezmoidata.toml")"
  [[ -n "$revision" ]] || { echo "Missing Oh My Zsh revision." >&2; exit 1; }
  if [[ ! -d "$omz" ]]; then
    git clone https://github.com/ohmyzsh/ohmyzsh.git "$omz"
    git -C "$omz" checkout --detach "$revision"
  fi
  [[ -f "$omz/oh-my-zsh.sh" ]] || { echo "Invalid Oh My Zsh installation: $omz" >&2; exit 1; }
  if [[ "$(git -C "$omz" rev-parse HEAD)" != "$revision" ]]; then
    if [[ -n "$(git -C "$omz" status --porcelain --untracked-files=no)" ]]; then
      echo "Oh My Zsh has local changes. Preserve them before aligning its revision." >&2
      exit 1
    fi
    git -C "$omz" fetch origin "$revision"
    git -C "$omz" checkout --detach "$revision"
  fi
}

install_profile_tools() {
  local installer
  [[ "$DOTFILES_PROFILE" == personal ]] || return
  command -v bws >/dev/null 2>&1 && return
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  curl -fsSL https://bws.bitwarden.com/install -o "$installer"
  /bin/sh "$installer"
}

main() {
  configure_homebrew
  install_homebrew_packages
  install_editor
  install_oh_my_zsh
  install_profile_tools
}
