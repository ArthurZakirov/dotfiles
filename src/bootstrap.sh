#!/bin/bash

module_dir="${DOTFILES_MODULE_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
source "$module_dir/homebrew.sh"

profile=""
github_username=""
dotfiles_source_dir=""
dotfiles_branch=""
backup_dir=""

usage() {
  cat <<'EOF'
Usage: GITHUB_USERNAME=<github-user> run_bootstrap.sh [personal|professional]

Optional environment variables:
  DOTFILES_SOURCE_DIR  Local checkout location.
  DOTFILES_BRANCH      Git branch to use. Omit it to follow the remote HEAD.
EOF
}

parse_arguments() {
  profile="${1:-personal}"
  case "$profile" in
    personal|professional) ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
}

load_configuration() {
  github_username="${GITHUB_USERNAME:-}"
  dotfiles_source_dir="${DOTFILES_SOURCE_DIR:-$HOME/Repos/personal/dotfiles}"
  dotfiles_branch="${DOTFILES_BRANCH:-}"
}

validate_environment() {
  [[ "$(uname -s)" == Darwin ]] || {
    echo "This setup requires macOS." >&2
    exit 1
  }
  [[ -n "$github_username" ]] || {
    echo "Set GITHUB_USERNAME to the GitHub account that owns the dotfiles repository." >&2
    exit 2
  }
}

install_homebrew() {
  local installer
  if [[ -x /opt/homebrew/bin/brew || -x /usr/local/bin/brew ]]; then
    return
  fi
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$installer"
  /bin/bash "$installer"
}

install_bootstrap_tools() {
  install_formulae chezmoi git
}

backup_existing_configuration() {
  local chezmoi_config="$HOME/.config/chezmoi/chezmoi.toml"
  backup_dir="$HOME/Library/Application Support/dotfiles/backups/$(date +%Y%m%d-%H%M%S)-$$"
  mkdir -p "$backup_dir"
  [[ ! -e "$HOME/.zshrc" ]] || cp -p "$HOME/.zshrc" "$backup_dir/zshrc"
  [[ ! -e "$chezmoi_config" ]] || cp -p "$chezmoi_config" "$backup_dir/chezmoi.toml"
}

initialize_chezmoi() {
  local init_args=(
    init
    --source "$dotfiles_source_dir"
    --prompt
    --promptChoice "Mac profile=$profile"
    --promptString "GitHub username=$github_username"
    --promptString 'Bitwarden Keychain account=bws-macbook-air'
  )
  if [[ -e "$dotfiles_source_dir" ]]; then
    [[ -f "$dotfiles_source_dir/.chezmoiroot" && -f "$dotfiles_source_dir/home/dot_zshrc.tmpl" ]] || {
      echo "Existing source directory is not this shell setup: $dotfiles_source_dir" >&2
      exit 1
    }
  else
    mkdir -p "$(dirname "$dotfiles_source_dir")"
    [[ -z "$dotfiles_branch" ]] || init_args+=(--branch "$dotfiles_branch")
    init_args+=("$github_username")
  fi
  chezmoi "${init_args[@]}"
}

apply_dotfiles() {
  chezmoi apply --force
}

validate_shell() {
  /bin/zsh -n "$HOME/.zshrc"
}

main() {
  parse_arguments "$@"
  load_configuration
  validate_environment
  install_homebrew
  configure_homebrew
  install_bootstrap_tools
  backup_existing_configuration
  initialize_chezmoi
  apply_dotfiles
  validate_shell
  echo "Shell setup complete ($profile). Backup: $backup_dir. Open a new terminal."
}
