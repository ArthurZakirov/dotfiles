#!/bin/bash
set -euo pipefail
[[ "$(uname -s)" == Darwin ]] || { echo "This setup requires macOS." >&2; exit 1; }
profile="${1:-personal}"
case "$profile" in personal|professional) ;; *) echo "Usage: bootstrap.sh [personal|professional]" >&2; exit 2;; esac
branch="${DOTFILES_BRANCH:-feat/mac-shell-bootstrap}"
source_dir="$HOME/Repos/personal/dotfiles"

if [[ ! -x /opt/homebrew/bin/brew && ! -x /usr/local/bin/brew ]]; then
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$installer"
  /bin/bash "$installer"
fi
if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
else
  eval "$(/usr/local/bin/brew shellenv)"
fi
command -v chezmoi >/dev/null 2>&1 || brew install chezmoi
command -v git >/dev/null 2>&1 || brew install git
if [[ ! -e "$source_dir" ]]; then
  mkdir -p "$(dirname "$source_dir")"
  git clone --branch "$branch" https://github.com/ArthurZakirov/dotfiles.git "$source_dir"
else
  [[ -f "$source_dir/.chezmoiroot" && -f "$source_dir/home/dot_zshrc.tmpl" ]] || {
    echo "Existing source directory has no shell setup. Update it manually, preserving local changes." >&2; exit 1;
  }
fi
# Preserve the old configuration before changing the managed shell.
backup_dir="$HOME/Library/Application Support/dotfiles/backups/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$backup_dir"
[[ ! -e "$HOME/.zshrc" ]] || cp -p "$HOME/.zshrc" "$backup_dir/zshrc"
config="$HOME/.config/chezmoi/chezmoi.toml"
[[ ! -e "$config" ]] || cp -p "$config" "$backup_dir/chezmoi.toml"
# Update the legacy default link only if it is the known broken link.
if [[ -L "$HOME/.local/share/chezmoi" && ! -e "$HOME/.local/share/chezmoi" && "$(readlink "$HOME/.local/share/chezmoi")" == "$HOME/Repos/dotfiles" ]]; then
  ln -sfn "$source_dir" "$HOME/.local/share/chezmoi"
fi
chezmoi init --source "$source_dir" --prompt --promptChoice "Mac profile=$profile" --promptString 'Bitwarden Keychain account=bws-macbook-air'
chezmoi apply --force
/bin/zsh -n "$HOME/.zshrc"
echo "Shell setup complete ($profile). Backup: $backup_dir. Open a new terminal."
