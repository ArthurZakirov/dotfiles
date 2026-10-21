#!/bin/bash
# Reuse a functional browser installed by agent-browser or an existing Chrome.
# An apply is not a browser updater: versions change only on explicit upgrade.

agent_browser_runtime_present() {
  local candidate
  for candidate in \
    "${AGENT_BROWSER_EXECUTABLE_PATH:-}" \
    "$HOME/.agent-browser/browsers"/chrome-*/"Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing" \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "$HOME/Library/Caches/ms-playwright"/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium \
    "$HOME/Library/Caches/ms-playwright"/chromium-*/chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium
  do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    if "$candidate" --version >/dev/null 2>&1; then
      printf 'Already available: browser runtime (%s)\n' "$candidate"
      return 0
    fi
  done
  return 1
}

ensure_agent_browser_runtime() {
  if agent_browser_runtime_present; then
    return 0
  fi
  printf 'Browser runtime missing; downloading Chrome for Testing ...\n'
  agent-browser install
}
