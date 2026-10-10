#!/bin/bash

install_homebrew() {
  local installer
  if [[ -x /opt/homebrew/bin/brew || -x /usr/local/bin/brew ]]; then
    return
  fi
  installer="$(mktemp)"
  if ! curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$installer"; then
    rm -f "$installer"
    return 1
  fi
  if ! /bin/bash "$installer"; then
    rm -f "$installer"
    return 1
  fi
  rm -f "$installer"
}

configure_homebrew() {
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  else
    echo "Homebrew was installed but its executable could not be found." >&2
    exit 1
  fi
}

install_formulae() {
  local formula
  for formula in "$@"; do
    command -v "$formula" >/dev/null 2>&1 || brew install "$formula"
  done
}
