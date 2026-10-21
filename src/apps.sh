#!/bin/bash
# Install profile-scoped apps only when the existing application or CLI is missing.
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

# Version requirements are declared in manifests, not hardcoded to Python.
binary_meets_minimum_version() {
  local executable="$1" requirement="$2" reported actual_major actual_minor required_major required_minor
  [[ "$requirement" =~ ^([0-9]+)\.([0-9]+)$ ]] || return 2
  required_major="${BASH_REMATCH[1]}"
  required_minor="${BASH_REMATCH[2]}"
  reported="$("$executable" --version 2>&1)" || return 1
  [[ "$reported" =~ ([0-9]+)\.([0-9]+) ]] || return 1
  actual_major="${BASH_REMATCH[1]}"
  actual_minor="${BASH_REMATCH[2]}"
  (( actual_major > required_major || (actual_major == required_major && actual_minor >= required_minor) ))
}

install_missing_formula() {
  local command_name="$1" formula="$2" minimum="${3:-}"
  if [[ -n "$command_name" ]] && command -v "$command_name" >/dev/null 2>&1; then
    if [[ -z "$minimum" ]] || binary_meets_minimum_version "$command_name" "$minimum"; then
      echo "Already installed: $command_name"
      return 0
    fi
  fi
  if brew list --formula "$formula" >/dev/null 2>&1; then
    if [[ -n "$minimum" ]]; then
      echo "Homebrew $formula is installed, but $command_name on PATH does not meet version >= $minimum. Fix PATH." >&2
      return 1
    fi
    if [[ -z "$command_name" ]]; then
      echo "Already installed: $formula (Homebrew)"
    else
      echo "Already installed: $formula (Homebrew; binary not on PATH)"
    fi
    return 0
  fi
  echo "Installing: $formula"
  brew install "$formula" || return
  if [[ -n "$minimum" ]] && { ! command -v "$command_name" >/dev/null 2>&1 || ! binary_meets_minimum_version "$command_name" "$minimum"; }; then
    echo "Installed $formula, but $command_name is still below version $minimum on PATH." >&2
    return 1
  fi
}

# The Brewfiles use valid brew/cask declarations with optional annotations.
# Keep the command/app checks in Bash: a plain 'brew bundle install' would not
# preserve the skip behavior for apps that were installed outside Homebrew.
install_brew_manifest() {
  local file="$1" line kind package check_type check_value post_action minimum
  local -a app_names
  local pattern='^(brew|cask)[[:space:]]+"([^"]+)"[[:space:]]+#[[:space:]]+(binary|apps):[[:space:]]*(.+)$'
  local formula_pattern='^brew[[:space:]]+"([^"]+)"$'
  [[ -r "$file" ]] || { echo "Missing Brewfile: $file" >&2; return 1; }
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in ''|\#*) continue ;; esac
    # Some formulae (e.g. shell plugins) expose no executable.
    if [[ "$line" =~ $formula_pattern ]]; then
      install_missing_formula "" "${BASH_REMATCH[1]}" || return
      continue
    fi
    if [[ ! "$line" =~ $pattern ]]; then
      echo "Invalid Brewfile entry in $file: $line" >&2
      return 2
    fi
    kind="${BASH_REMATCH[1]}"
    package="${BASH_REMATCH[2]}"
    check_type="${BASH_REMATCH[3]}"
    check_value="${BASH_REMATCH[4]}"
    post_action=""
    minimum=""
    if [[ "$check_value" == *"; min-version: "* ]]; then
      minimum="${check_value##*; min-version: }"
      check_value="${check_value%%; min-version: *}"
      [[ "$minimum" =~ ^[0-9]+\.[0-9]+$ ]] || { echo "Invalid minimum version in $file" >&2; return 2; }
    fi
    if [[ "$check_value" == *"; post: "* ]]; then
      post_action="${check_value##*; post: }"
      check_value="${check_value%%; post: *}"
      [[ -n "$post_action" ]] || { echo "Missing post-install action in $file" >&2; return 2; }
    fi
    [[ -z "$minimum" || "$kind/$check_type" == brew/binary ]] || { echo "Minimum version is supported only for formula binaries in $file" >&2; return 2; }
    case "$kind/$check_type" in
      brew/binary)
        install_missing_formula "$check_value" "$package" "$minimum" || return
        ;;
      cask/binary)
        install_missing_cli_cask "$check_value" "$package" || return
        ;;
      cask/apps)
        IFS='|' read -r -a app_names <<< "$check_value"
        install_missing_cask "$package" "${app_names[@]}" || return
        ;;
      *)
        echo "Unsupported Brewfile entry in $file: $line" >&2
        return 2
        ;;
    esac
    if [[ -n "$post_action" ]]; then
      PENDING_BREW_ACTIONS+=("$post_action")
    fi
  done < "$file"
}

# npm installs are global, and an existing CLI is never upgraded or replaced.
install_npm_cli() {
  local command_name="$1" package="$2" verification="$3"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    command -v npm >/dev/null 2>&1 || {
      echo "npm is required to install $package." >&2
      return 127
    }
    if npm list --global --depth=0 "$package" >/dev/null 2>&1; then
      echo "Already installed: $package (npm; executable $command_name is not on PATH)" >&2
      return 1
    fi
    echo "Installing: $package (npm)"
    npm install --global "$package" || return 1
  fi
  if [[ "$verification" == version ]]; then
    "$command_name" --version >/dev/null 2>&1 || {
      echo "$command_name failed its version check." >&2
      return 1
    }
  fi
}

install_npm_manifest() {
  local file="$1" command_name package verification post_action extra
  [[ -r "$file" ]] || { echo "Missing npm manifest: $file" >&2; return 1; }
  while read -r command_name package verification post_action extra || [[ -n "$command_name" ]]; do
    case "$command_name" in ''|\#*) continue ;; esac
    if [[ -z "$package" || ( "$verification" != version && "$verification" != none ) || -n "$extra" ]]; then
      echo "Invalid npm manifest entry in $file: $command_name $package $verification $post_action $extra" >&2
      return 2
    fi
    install_npm_cli "$command_name" "$package" "$verification" || return
    if [[ -n "$post_action" && "$post_action" != none ]]; then
      run_dependency_post_install "$post_action" || return
    fi
  done < "$file"
}

# Profile and package membership are declared under dependencies/.
install_manifest_dependencies() {
  local scope="$1" category file
  PENDING_BREW_ACTIONS=()
  for category in cli gui; do
    file="$DOTFILES_ROOT/dependencies/brew/$scope/$category.Brewfile"
    [[ -f "$file" ]] || continue
    install_brew_manifest "$file" || return
  done
  file="$DOTFILES_ROOT/dependencies/npm/$scope.txt"
  if [[ -f "$file" ]]; then
    install_npm_manifest "$file" || return
  fi
}

run_pending_brew_actions() {
  local action
  for action in "${PENDING_BREW_ACTIONS[@]-}"; do
    [[ -n "$action" ]] || continue
    run_dependency_post_install "$action" || return
  done
  PENDING_BREW_ACTIONS=()
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
