#!/bin/bash
# Install common macOS apps only when no existing installation is found.

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

install_common_apps() {
  install_missing_cask alt-tab 'AltTab.app'
  install_missing_cask betterdisplay 'BetterDisplay.app'
  install_missing_cask displaylink 'DisplayLink Manager.app'
  install_missing_cli_cask codex codex
  install_missing_cli_cask claude claude-code
  install_missing_cask ddpm 'DDPM/DDPM.app'
  install_missing_cask warp 'Warp.app'
  install_missing_cask google-drive 'Google Drive.app'
  install_missing_cask hammerspoon 'Hammerspoon.app'
  install_missing_cask logi-options+ 'Logi Options+.app' 'logioptionsplus.app'
  install_missing_cask logitune 'LogiTune.app' 'Logi Tune.app'
  install_missing_cask docker-desktop 'Docker.app'
  install_missing_formula node node
  install_missing_cask raycast 'Raycast.app'
  install_missing_cask rectangle 'Rectangle.app'
  install_missing_cask visual-studio-code 'Visual Studio Code.app'
}
