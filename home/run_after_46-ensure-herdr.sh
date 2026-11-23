#!/bin/bash
set -euo pipefail
[[ "$(uname -s)" == Darwin ]] || exit 0
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ ! -x "$HOME/.local/bin/herdr-app" ]]; then
  if [[ "$(sysctl -in hw.optional.arm64)" != 1 ]]; then
    echo "Herdr provides prebuilt Mac releases for Apple Silicon only; skipping Herdr installation." >&2
    exit 0
  fi
  installer=$(mktemp)
  trap 'rm -f "$installer"' EXIT
  curl -fsSL --retry 3 https://releases.herdr.dev/app/install.sh -o "$installer"
  /bin/sh "$installer"
fi
if ! command -v herdr-core >/dev/null; then
  installer=$(mktemp)
  trap 'rm -f "$installer"' EXIT
  curl -fsSL --retry 3 https://releases.herdr.dev/core/install.sh -o "$installer"
  HC_INSTALL_DIR="$HOME/.local/bin" /bin/sh "$installer"
fi
venv="$HOME/.local/share/herdr-history-venv"
if [[ ! -x "$venv/bin/python" ]]; then
  uv venv "$venv" --python python3
fi
uv pip install --python "$venv/bin/python" 'rich==15.0.0' 'pygments==2.21.0' 'markdown-it-py==4.3.0' 'mdurl==0.1.2'
