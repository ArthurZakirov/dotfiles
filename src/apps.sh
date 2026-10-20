#!/bin/bash
# Install optional apps only when the existing application or CLI is missing.
# Package identities live in Brewfiles and npm manifests, not in shell code.

app_exists() {
  local name
  for name in "$@"; do
    [[ -d "/Applications/$name" || -d "$HOME/Applications/$name" ]] && return 0
  done
  return 1
}

install_missing_cask() {
  local cask="$1"; shift
  # Existing Homebrew installations can contain pkg-installed apps in vendor directories.
  if brew list --cask "$cask" >/dev/null 2>&1; then
    echo "Already installed: $cask (Homebrew)"
    return 0
  fi
  if (( $# > 0 )) && app_exists "$@"; then
    echo "Already installed: $cask (application)"
    return 0
  fi
  echo "Installing: $cask"
  brew install --cask "$cask"
}

install_missing_cli_cask() {
  local command_name="$1" cask="$2"
  if command -v "$command_name" >/dev/null 2>&1; then
    echo "Already installed: $command_name"
    return 0
  fi
  install_missing_cask "$cask"
}

install_missing_formula() {
  local command_name="$1" formula="$2"
  if command -v "$command_name" >/dev/null 2>&1; then
    echo "Already installed: $command_name"
    return 0
  fi
  echo "Installing: $formula"
  brew install "$formula"
}

# The optional Brewfiles use valid brew/cask declarations with annotations.
# Keep the command/app checks in Bash: a plain 'brew bundle install' would not
# preserve the skip behavior for apps that were installed outside Homebrew.
install_optional_brewfile() {
  local file="$1" line kind package check_type check_value
  local -a app_names
  local pattern='^(brew|cask)[[:space:]]+"([^"]+)"[[:space:]]+#[[:space:]]+(binary|apps):[[:space:]]*(.+)$'
  [[ -r "$file" ]] || { echo "Missing Brewfile: $file" >&2; return 1; }
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in ''|\#*) continue ;; esac
    if [[ ! "$line" =~ $pattern ]]; then
      echo "Invalid optional Brewfile entry in $file: $line" >&2
      return 2
    fi
    kind="${BASH_REMATCH[1]}"
    package="${BASH_REMATCH[2]}"
    check_type="${BASH_REMATCH[3]}"
    check_value="${BASH_REMATCH[4]}"
    case "$kind/$check_type" in
      brew/binary)
        install_missing_formula "$check_value" "$package" || return
        ;;
      cask/binary)
        install_missing_cli_cask "$check_value" "$package" || return
        ;;
      cask/apps)
        IFS='|' read -r -a app_names <<< "$check_value"
        install_missing_cask "$package" "${app_names[@]}" || return
        ;;
      *)
        echo "Unsupported optional Brewfile entry in $file: $line" >&2
        return 2
        ;;
    esac
  done < "$file"
}

# npm installs are global, and an existing CLI is never upgraded or replaced.
install_npm_cli() {
  local command_name="$1" package="$2" verification="$3"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    if [[ "$command_name" == desktop-commander ]] && ! command -v npm >/dev/null 2>&1; then
      echo 'npm is required to install Desktop Commander.' >&2
      return 1
    fi
    case "$command_name" in
      skills) echo 'Installing: Vercel skills CLI (npm)' ;;
      agent-browser) echo 'Installing: agent-browser (npm)' ;;
      *) echo "Installing: $package (npm)" ;;
    esac
    npm install --global "$package" || return 1
  fi
  if [[ "$verification" == version ]]; then
    "$command_name" --version >/dev/null 2>&1 || {
      case "$command_name" in
        skills) echo 'Vercel skills CLI failed its version check.' >&2 ;;
        agent-browser) echo 'Agent Browser CLI failed its version check.' >&2 ;;
        *) echo "$command_name failed its version check." >&2 ;;
      esac
      return 1
    }
  fi
}

install_npm_manifest() {
  local file="$1" command_name package verification extra
  [[ -r "$file" ]] || { echo "Missing npm manifest: $file" >&2; return 1; }
  while read -r command_name package verification extra || [[ -n "$command_name" ]]; do
    case "$command_name" in ''|\#*) continue ;; esac
    if [[ -z "$package" || ( "$verification" != version && "$verification" != none ) || -n "$extra" ]]; then
      echo "Invalid npm manifest entry in $file: $command_name $package $verification $extra" >&2
      return 2
    fi
    install_npm_cli "$command_name" "$package" "$verification" || return
  done < "$file"
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

install_common_apps() {
  install_optional_brewfile "$DOTFILES_ROOT/brew/common/gui.Brewfile" || return
  install_optional_brewfile "$DOTFILES_ROOT/brew/common/cli.Brewfile" || return
  install_npm_manifest "$DOTFILES_ROOT/npm/common.txt"
}

# Only the personal profile installs these apps.
install_personal_apps() {
  install_optional_brewfile "$DOTFILES_ROOT/brew/personal/gui.Brewfile" || return
  install_optional_brewfile "$DOTFILES_ROOT/brew/personal/cli.Brewfile" || return
  install_npm_manifest "$DOTFILES_ROOT/npm/personal.txt" || return
  configure_desktop_commander_cli
}

verify_node_toolchain() {
  local tool
  for tool in node npm npx; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      echo "Missing $tool after Node.js installation." >&2
      return 1
    fi
  done
}
