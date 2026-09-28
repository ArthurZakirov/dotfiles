#!/bin/sh
set -eu

[ "$(uname -s)" = "Darwin" ] || exit 0

package='@wonderwhy-er/desktop-commander'
version='0.2.51'

if ! command -v npm >/dev/null 2>&1; then
  echo "Desktop Commander requires npm. Install Node.js before applying these dotfiles." >&2
  exit 1
fi

if ! npm ls -g "$package@$version" --depth=0 >/dev/null 2>&1; then
  npm install -g "$package@$version"
fi
