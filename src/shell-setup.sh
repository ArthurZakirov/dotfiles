#!/bin/bash

: "${DOTFILES_ROOT:?DOTFILES_ROOT must point to the dotfiles checkout}"
: "${DOTFILES_PROFILE:?DOTFILES_PROFILE must be personal or professional}"
module_dir="${DOTFILES_MODULE_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
source "$module_dir/homebrew.sh"
source "$module_dir/apps.sh"

install_homebrew_packages() {
  export PATH="$HOME/.local/bin:$PATH"
  brew bundle install --no-upgrade --file="$DOTFILES_ROOT/Brewfile"
}

install_visual_studio_code() {
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

install_editors() {
  install_visual_studio_code
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

install_bitwarden_secrets_manager() {
  local installer
  command -v bws >/dev/null 2>&1 && return 0
  installer="$(mktemp)"
  if ! curl -fsSL https://bws.bitwarden.com/install -o "$installer"; then
    rm -f "$installer"
    return 1
  fi
  if ! /bin/sh "$installer"; then
    rm -f "$installer"
    return 1
  fi
  rm -f "$installer"
}

install_personal_profile() {
  install_bitwarden_secrets_manager
}

install_professional_profile() {
  : # No professional-only tools yet.
}

install_profile() {
  case "$DOTFILES_PROFILE" in
    personal) install_personal_profile ;;
    professional) install_professional_profile ;;
    *) echo "Unsupported Mac profile: $DOTFILES_PROFILE" >&2; return 2 ;;
  esac
}

main() {
  [[ "$(uname -s)" == Darwin ]] || {
    echo "This dotfiles setup currently requires macOS." >&2
    return 1
  }
  case "$DOTFILES_PROFILE" in
    personal|professional) ;;
    *) echo "Unsupported Mac profile: $DOTFILES_PROFILE" >&2; return 2 ;;
  esac
  install_homebrew
  configure_homebrew
  install_homebrew_packages
  install_common_apps
  install_editors
  install_oh_my_zsh
  install_profile
}
