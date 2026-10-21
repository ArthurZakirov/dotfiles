#!/bin/bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$root/src/agent-browser-runtime.sh"
trial="$(mktemp -d)"
trap 'rm -rf "$trial"' EXIT
export HOME="$trial/home"
mkdir -p "$HOME/.agent-browser/browsers/chrome-155/Google Chrome for Testing.app/Contents/MacOS"
browser="$HOME/.agent-browser/browsers/chrome-155/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
printf '#!/bin/sh\n[ "$1" = --version ]\n' > "$browser"
chmod +x "$browser"
agent-browser() { echo "Unexpected download: $*" >&2; return 90; }
ensure_agent_browser_runtime >/dev/null
ensure_agent_browser_runtime >/dev/null
test -f "$browser"
rm -f "$browser"
export AGENT_BROWSER_EXECUTABLE_PATH="$trial/existing-chrome"
printf '#!/bin/sh\n[ "$1" = --version ]\n' > "$AGENT_BROWSER_EXECUTABLE_PATH"
chmod +x "$AGENT_BROWSER_EXECUTABLE_PATH"
ensure_agent_browser_runtime >/dev/null
unset AGENT_BROWSER_EXECUTABLE_PATH
echo 'Browser runtime: repeated installs skipped and explicit binary reused'
