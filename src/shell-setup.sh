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

configure_vscode_cli() {
  local app cli target
  if command -v code >/dev/null 2>&1; then
    code --version >/dev/null 2>&1 || {
      echo "Existing code CLI failed its version check." >&2
      return 1
    }
    return 0
  fi

  app="/Applications/Visual Studio Code.app"
  [[ -d "$app" ]] || app="$HOME/Applications/Visual Studio Code.app"
  cli="$app/Contents/Resources/app/bin/code"
  if [[ ! -f "$cli" ]]; then
    echo "VS Code CLI not found at $cli" >&2
    return 1
  fi
  mkdir -p "$HOME/.local/bin"
  target="$HOME/.local/bin/code"
  if [[ -L "$target" && ! -e "$target" ]]; then
    rm "$target"
  fi
  if [[ -e "$target" || -L "$target" ]]; then
    if [[ -x "$target" ]] && "$target" --version >/dev/null 2>&1; then
      return 0
    fi
    echo "Cannot create code CLI: $target already exists but is unusable." >&2
    return 1
  fi
  ln -s "$cli" "$target"
  PATH="$HOME/.local/bin:$PATH" code --version >/dev/null 2>&1 || {
    echo "VS Code CLI failed its version check after linking." >&2
    return 1
  }
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
  if [[ "${DOTFILES_SKIP_OPTIONAL_APPS:-}" != 1 ]]; then
    install_personal_apps
  fi
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
  # GitHub's ephemeral runners test rendering and shell provisioning, not GUI
  # downloads. Regular Macs always execute the full application setup.
  if [[ "${DOTFILES_SKIP_OPTIONAL_APPS:-}" != 1 ]]; then
    install_common_apps
    verify_node_toolchain
    configure_vscode_cli
  fi
  install_oh_my_zsh
  install_profile
}
