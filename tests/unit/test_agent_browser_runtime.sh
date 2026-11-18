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

# Check the managed entry point from independent processes and project directories.
mkdir -p "$trial/bin" "$trial/other-project"
cat > "$trial/bin/agent-browser" <<'STUB'
#!/bin/sh
if [ "${CHROME_TEST_DISCOVERY_DENIED:-0}" = 1 ]; then
  echo 'No running debuggable Chrome found (discovery inaccessible)' >&2
  exit 7
fi
printf '%s\n' "$@"
exit "${BROWSER_TEST_EXIT:-0}"
STUB
chmod +x "$trial/bin/agent-browser"
export PATH="$trial/bin:$PATH"
entrypoint="$root/home/dot_local/bin/executable_agent-chrome"
# Exercise launch and restricted inspection without touching the user's Chrome.
cat > "$trial/bin/uname" <<'STUB'
#!/bin/sh
printf '%s\n' "${CHROME_TEST_OS:-Darwin}"
STUB
cat > "$trial/bin/pgrep" <<'STUB'
#!/bin/sh
case "${CHROME_TEST_PROCESS:-running}" in
  running) exit 0 ;;
  closed) [ -f "$CHROME_TEST_LAUNCH" ] && exit 0; exit 1 ;;
  never) exit 1 ;;
  denied) echo 'process inspection denied' >&2; exit 3 ;;
  denied-one) echo 'process inspection denied' >&2; exit 1 ;;
esac
STUB
cat > "$trial/bin/open" <<'STUB'
#!/bin/sh
[ "$#" -eq 2 ] && [ "$1" = -a ] && [ "$2" = 'Google Chrome' ] || exit 99
[ "${CHROME_TEST_LAUNCH_FAIL:-0}" = 0 ] || exit 1
touch "$CHROME_TEST_LAUNCH"
STUB
chmod +x "$trial/bin/uname" "$trial/bin/pgrep" "$trial/bin/open"
export CHROME_TEST_LAUNCH="$trial/launched"

expected="$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab tab new 'https://example.com/?q=with space')"
for project in "$trial" "$trial/other-project"; do
  output="$(cd "$project" && AGENT_BROWSER_SESSION=per-chat "$entrypoint" tab new 'https://example.com/?q=with space')"
  [[ "$output" == "$expected" ]]
done

result=0
BROWSER_TEST_EXIT=42 "$entrypoint" click '@e1' > "$trial/attempt" || result=$?
[[ "$result" == 42 ]]
[[ "$(cat "$trial/attempt")" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab click '@e1')" ]]

for state in running closed denied denied-one; do
  rm -f "$CHROME_TEST_LAUNCH"
  CHROME_TEST_PROCESS="$state" "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error"
  [[ "$(cat "$trial/attempt")" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab tab list)" ]]
  if [[ "$state" == closed ]]; then
    test -f "$CHROME_TEST_LAUNCH"
  else
    test ! -f "$CHROME_TEST_LAUNCH"
  fi
  if [[ "$state" == denied* ]]; then
    [[ "$(cat "$trial/error")" == *'browser state unknown'* ]]
  fi
done
rm -f "$CHROME_TEST_LAUNCH"
result=0
CHROME_TEST_PROCESS=closed CHROME_TEST_LAUNCH_FAIL=1 "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error" || result=$?
[[ "$result" == 1 ]]
test ! -s "$trial/attempt"
for command in skills --help --version close; do
  CHROME_TEST_PROCESS=closed "$entrypoint" "$command" >/dev/null
  test ! -f "$CHROME_TEST_LAUNCH"
done
CHROME_TEST_OS=Linux CHROME_TEST_PROCESS=closed "$entrypoint" tab list >/dev/null
test ! -f "$CHROME_TEST_LAUNCH"
echo 'Chrome entrypoint: closed launched, running reused, denied distinguished, launch failure bounded'

# A running Chrome with inaccessible discovery must not cause another launch.
rm -f "$CHROME_TEST_LAUNCH"
result=0
CHROME_TEST_PROCESS=running CHROME_TEST_DISCOVERY_DENIED=1 "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error" || result=$?
[[ "$result" == 7 ]]
test ! -f "$CHROME_TEST_LAUNCH"
[[ "$(cat "$trial/error")" == *'discovery inaccessible'* ]]
# Successful open without an observable process cannot wait indefinitely.
cat > "$trial/bin/sleep" <<'STUB'
#!/bin/sh
echo tick >> "$CHROME_TEST_WAIT"
STUB
chmod +x "$trial/bin/sleep"
export CHROME_TEST_WAIT="$trial/wait"
CHROME_TEST_PROCESS=never "$entrypoint" tab list >/dev/null
[[ "$(wc -l < "$CHROME_TEST_WAIT" | tr -d ' ')" == 10 ]]
