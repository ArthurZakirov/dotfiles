#!/bin/bash
# Package-specific installation actions, independent of profile membership.

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


configure_desktop_commander_cli() {
  local cli target
  cli="$(command -v desktop-commander 2>/dev/null || true)"
  if [[ -z "$cli" ]] && command -v npm >/dev/null 2>&1; then
    cli="$(npm prefix --global)/bin/desktop-commander"
  fi
  if [[ -z "$cli" || ! -x "$cli" ]]; then
    echo 'Desktop Commander binary not found after npm installation.' >&2
    return 1
  fi
  target="$HOME/.local/bin/desktop-commander-remote"
  mkdir -p "$(dirname "$target")"
  if [[ -e "$target" && ! -L "$target" ]]; then
    echo "Refusing to overwrite $target" >&2
    return 1
  fi
  ln -sfn "$cli" "$target"
}

run_dependency_post_install() {
  case "$1" in
    desktop-commander-link) configure_desktop_commander_cli ;;
    vscode-cli) configure_vscode_cli ;;
    *) echo "Unsupported post-install action: $1" >&2; return 2 ;;
  esac
}

install_oh_my_zsh() {
  local revision="$1" omz="$HOME/.oh-my-zsh"
  [[ "$revision" =~ ^[[:xdigit:]]{40}$ ]] || {
    echo 'Invalid Oh My Zsh commit in dependency manifest.' >&2
    return 2
  }
  if [[ ! -d "$omz" ]]; then
    git clone https://github.com/ohmyzsh/ohmyzsh.git "$omz"
    git -C "$omz" checkout --detach "$revision"
  fi
  [[ -f "$omz/oh-my-zsh.sh" ]] || { echo "Invalid Oh My Zsh installation: $omz" >&2; return 1; }
  if [[ "$(git -C "$omz" rev-parse HEAD)" != "$revision" ]]; then
    if [[ -n "$(git -C "$omz" status --porcelain --untracked-files=no)" ]]; then
      echo 'Oh My Zsh has local changes. Preserve them before aligning its revision.' >&2
      return 1
    fi
    git -C "$omz" fetch origin "$revision"
    git -C "$omz" checkout --detach "$revision"
  fi
}

install_git_dependencies() {
  local scope="$1" file name revision
  for file in "$DOTFILES_ROOT/dependencies/git/$scope/"*.commit; do
    [[ -f "$file" ]] || continue
    name="${file##*/}"
    name="${name%.commit}"
    revision="$(cat "$file")"
    case "$name" in
      oh-my-zsh) install_oh_my_zsh "$revision" || return ;;
      *) echo "Unsupported Git dependency: $name" >&2; return 2 ;;
    esac
  done
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

install_manual_dependencies() {
  local scope="$1" file name
  file="$DOTFILES_ROOT/dependencies/manual/$scope.txt"
  [[ -f "$file" ]] || return 0
  while IFS= read -r name || [[ -n "$name" ]]; do
    case "$name" in
      ''|\#*) continue ;;
      bitwarden-secrets-manager) install_bitwarden_secrets_manager || return ;;
      *) echo "Unsupported manual dependency: $name" >&2; return 2 ;;
    esac
  done < "$file"
}
