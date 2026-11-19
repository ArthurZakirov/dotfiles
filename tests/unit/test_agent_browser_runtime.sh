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
if [ "${CHROME_TEST_COPY_STDIN:-0}" = 1 ]; then
  cat > "$CHROME_TEST_STDIN_COPY"
fi
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
  final-wait)
    [ -f "$CHROME_TEST_WAIT" ] && [ "$(wc -l < "$CHROME_TEST_WAIT")" -ge 10 ] && exit 0
    exit 1
    ;;
  closed-denied)
    if [ -f "$CHROME_TEST_LAUNCH" ]; then
      echo 'process inspection denied after launch' >&2
      exit 3
    fi
    exit 1
    ;;
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
for command in skills --help --version close quit exit; do
  CHROME_TEST_PROCESS=closed "$entrypoint" "$command" >/dev/null
  test ! -f "$CHROME_TEST_LAUNCH"
  CHROME_TEST_PROCESS=closed "$entrypoint" --json "$command" >/dev/null
  test ! -f "$CHROME_TEST_LAUNCH"
done
output="$(CHROME_TEST_PROCESS=closed "$entrypoint" --json skills get core)"
[[ "$output" == "$(printf '%s\n' --session dotfiles-chrome --pin-tab --json skills get core)" ]]
test ! -f "$CHROME_TEST_LAUNCH"
for metadata_flag in --help -h --version -V; do
  CHROME_TEST_PROCESS=closed "$entrypoint" snapshot "$metadata_flag" >/dev/null
  test ! -f "$CHROME_TEST_LAUNCH"
  CHROME_TEST_PROCESS=closed "$entrypoint" --json tab list "$metadata_flag" >/dev/null
  test ! -f "$CHROME_TEST_LAUNCH"
  CHROME_TEST_PROCESS=closed "$entrypoint" snapshot -- "$metadata_flag" >/dev/null
  test ! -f "$CHROME_TEST_LAUNCH"
done
# Audit all installed 0.39 global prefix families, including optional booleans.
# Each invocation must preserve argv; only browser work may launch Chrome.
assert_launch_behavior() {
  local should_launch="$1" output
  shift
  rm -f "$CHROME_TEST_LAUNCH"
  output="$(CHROME_TEST_PROCESS=closed "$entrypoint" "$@")"
  if [[ "$should_launch" == browserless ]]; then
    [[ "$output" == "$(printf '%s\n' --session dotfiles-chrome --pin-tab "$@")" ]]
  else
    [[ "$output" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab "$@")" ]]
  fi
  if [[ "$should_launch" == yes ]]; then
    test -f "$CHROME_TEST_LAUNCH"
  else
    test ! -f "$CHROME_TEST_LAUNCH"
  fi
}
for flag in --json --headed --webgpu --no-webmcp --debug \
  --ignore-https-errors --allow-file-access --hide-scrollbars --auto-connect \
  --pin-tab --no-pin-tab --no-ca-cert --use-system-ca --annotate \
  --content-boundaries --confirm-interactive --no-auto-dialog \
  -v --verbose -q --quiet --offline --quick --fix; do
  for value in absent true false; do
    prefix=("$flag")
    [[ "$value" == absent ]] || prefix+=("$value")
    assert_launch_behavior browserless "${prefix[@]}" skills get core
    assert_launch_behavior browserless "${prefix[@]}" quit
    if [[ "$flag" == --webgpu && "$value" != false ]]; then
      assert_launch_behavior no "${prefix[@]}" tab list
    else
      assert_launch_behavior yes "${prefix[@]}" tab list
    fi
  done
done
for flag in --session --restore-save --restore-check-url --restore-check-text \
  --restore-check-fn --namespace --headers --executable-path --cdp \
  --extension --init-script --enable --profile --state --proxy --proxy-bypass \
  --args --user-agent -p --provider --device --session-name --color-scheme \
  --download-path --max-output --allowed-domains --action-policy \
  --confirm-actions --config --engine --input-mode --screenshot-dir \
  --screenshot-quality --screenshot-format --idle-timeout --ca-cert --model; do
  # A command-shaped value is still an option value, never the actual command.
  assert_launch_behavior browserless "$flag" 'value with space' skills get core
  case "$flag" in
    --cdp|-p|--provider|--ca-cert) assert_launch_behavior no "$flag" skills tab list ;;
    *) assert_launch_behavior yes "$flag" skills tab list ;;
  esac
  assert_launch_behavior no "$flag"
done
for command in install upgrade doctor dashboard profiles plugin plugins mcp session; do
  assert_launch_behavior browserless --debug --max-output 100 "$command"
done
for subcommand in list show clear clean rename; do
  assert_launch_behavior browserless state "$subcommand" example
  assert_launch_behavior browserless --debug state --json false "$subcommand" example
  assert_launch_behavior browserless --max-output 100 state --max-output 20 "$subcommand" example
done
for subcommand in save load; do
  assert_launch_behavior yes state "$subcommand" example
  assert_launch_behavior yes --json false state --max-output 100 "$subcommand" example
done
for subcommand in save show delete list; do
  assert_launch_behavior browserless --json auth "$subcommand" example
done
assert_launch_behavior yes auth login example
for command in device stream confirm deny; do
  assert_launch_behavior browserless "$command"
done
assert_launch_behavior browserless stream status
assert_launch_behavior browserless webmcp result example
assert_launch_behavior browserless --json webmcp cancel example
assert_launch_behavior yes webmcp list
assert_launch_behavior yes webmcp invoke example
assert_launch_behavior browserless network har stop example.har
assert_launch_behavior browserless network --json har --max-output 100 stop example.har
assert_launch_behavior yes network har start
assert_launch_behavior yes network requests
for command in open goto navigate press key scrollintoview scrollinto; do
  assert_launch_behavior yes --debug false --max-output 100 "$command" example
  assert_launch_behavior browserless --debug false --max-output 100 "$command" --help
done
assert_launch_behavior browserless read https://example.com
assert_launch_behavior browserless --json read --raw https://example.com
assert_launch_behavior yes read
assert_launch_behavior yes read --filter 'text is not a URL'
assert_launch_behavior browserless read --filter 'text with space' --timeout 1000 --raw https://example.com
assert_launch_behavior browserless --max-output 100 read --json false --llms index https://example.com
assert_launch_behavior browserless batch 'read https://example.com' 'read https://example.org'
# Batch is passed through without inspecting or consuming stdin, including
# mixed browser operations. Connect with tab list first when Chrome is closed.
assert_launch_behavior browserless batch 'open https://example.com' snapshot
export CHROME_TEST_STDIN_COPY="$trial/stdin-copy"
printf '%s' '[["read", "https://example.com"], ["read", "https://example.org"]]' > "$trial/stdin"
CHROME_TEST_COPY_STDIN=1 CHROME_TEST_PROCESS=closed "$entrypoint" batch < "$trial/stdin" >/dev/null
cmp "$trial/stdin" "$CHROME_TEST_STDIN_COPY"
test ! -f "$CHROME_TEST_LAUNCH"
assert_launch_behavior no snapshot --webgpu
assert_launch_behavior no snapshot --webgpu true
assert_launch_behavior yes snapshot --webgpu false
assert_launch_behavior yes --webgpu snapshot --webgpu false
assert_launch_behavior no --webgpu false snapshot --webgpu true
assert_launch_behavior no snapshot --cdp 9222
assert_launch_behavior no snapshot --provider example
assert_launch_behavior no snapshot --ca-cert example.pem
assert_launch_behavior yes --ca-cert example.pem snapshot --no-ca-cert
assert_launch_behavior no --no-ca-cert snapshot --ca-cert example.pem
assert_launch_behavior yes --user-agent --webgpu snapshot
assert_launch_behavior no --json false
assert_launch_behavior no --restore skills get core
assert_launch_behavior no --restore example-key skills get core
assert_launch_behavior no --restore=example-key skills get core
assert_launch_behavior no --unknown-future-option skills get core
rm -f "$CHROME_TEST_LAUNCH"
CHROME_TEST_OS=Linux CHROME_TEST_PROCESS=closed "$entrypoint" tab list >/dev/null
test ! -f "$CHROME_TEST_LAUNCH"

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
result=0
CHROME_TEST_PROCESS=never "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error" || result=$?
[[ "$result" == 1 ]]
test ! -s "$trial/attempt"
[[ "$(cat "$trial/error")" == *'did not become observable'* ]]
[[ "$(wc -l < "$CHROME_TEST_WAIT" | tr -d ' ')" == 10 ]]
rm -f "$CHROME_TEST_LAUNCH" "$CHROME_TEST_WAIT"
CHROME_TEST_PROCESS=final-wait "$entrypoint" tab list > "$trial/attempt"
[[ "$(wc -l < "$CHROME_TEST_WAIT" | tr -d ' ')" == 10 ]]
[[ "$(cat "$trial/attempt")" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab tab list)" ]]
rm -f "$CHROME_TEST_LAUNCH"
CHROME_TEST_PROCESS=closed-denied "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error"
[[ "$(cat "$trial/error")" == *'browser state unknown'* ]]
[[ "$(cat "$trial/attempt")" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab tab list)" ]]
echo 'Chrome entrypoint: closed launched, running reused, denied distinguished, launch failure bounded'
