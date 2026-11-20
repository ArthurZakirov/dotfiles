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
if [ "${CHROME_TEST_DIRECT:-0}" = 1 ]; then
  printf '%s\n' "$*" >> "$CHROME_TEST_TRACE"
  case "$*" in
    *' connect '*)
      [ "${CHROME_TEST_CONNECT_FAIL:-0}" = 0 ] || { echo 'connection refused' >&2; exit 1; }
      touch "$CHROME_TEST_CONNECTED"
      echo connected
      exit 0
      ;;
    *'--auto-connect'*)
      if [ ! -f "$CHROME_TEST_CONNECTED" ]; then
        echo 'No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp.' >&2
        exit 1
      fi
      ;;
  esac
  if [ "${CHROME_TEST_VERIFY_FAIL:-0}" = 1 ]; then
    echo 'tab access denied' >&2
    exit 1
  fi
fi
if [ "${CHROME_TEST_DISCOVERY_DENIED:-0}" = 1 ]; then
  echo 'No running debuggable Chrome found (discovery inaccessible)' >&2
  exit 7
fi
if [ "${CHROME_TEST_COPY_STDIN:-0}" = 1 ]; then
  cat > "$CHROME_TEST_STDIN_COPY"
  if [ -f "$CHROME_TEST_LAUNCH" ]; then
    cp "$CHROME_TEST_STDIN_COPY" "$CHROME_TEST_STDIN_COPY.after"
  else
    cp "$CHROME_TEST_STDIN_COPY" "$CHROME_TEST_STDIN_COPY.before"
  fi
fi
if [ "${CHROME_TEST_CONNECT_BEFORE_LAUNCH:-0}" = 1 ] && [ ! -f "$CHROME_TEST_LAUNCH" ]; then
  case "${CHROME_TEST_JSON_DISCOVERY:-0}" in
    1) echo '{"error":"No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp.","success":false}' ;;
    2) echo '{"success":false,"error":"No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp."}' ;;
    3) printf '\033[31m✗\033[0m No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp.\n' >&2 ;;
    4) echo 'Error: No running debuggable Chrome found' >&2 ;;
    5) echo '✗ Auto-launch failed: No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp.' >&2 ;;
    7) echo 'Warning: ignoring unsupported project setting' >&2
       echo '✗ Auto-launch failed: No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp.' >&2 ;;
    6) echo '{"error":"Auto-launch failed: No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp.","settings":{"applied":false},"success":false}' ;;
    *) echo 'No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp.' >&2 ;;
  esac
  exit 1
fi
if [ -n "${BROWSER_TEST_JSON_ERROR:-}" ]; then
  printf '%s\n' "$BROWSER_TEST_JSON_ERROR"
  exit "${BROWSER_TEST_EXIT:-1}"
fi
if [ -n "${BROWSER_TEST_ERROR:-}" ]; then
  printf '%s\n' "$BROWSER_TEST_ERROR" >&2
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
cat > "$trial/bin/lsof" <<'STUB'
#!/bin/sh
[ "${CHROME_TEST_DIRECT:-0}" = 1 ] || exit 1
printf '%s\n' "$*" > "$CHROME_TEST_LSOF_ARGS"
[ "${CHROME_TEST_LSOF_FAIL:-0}" = 0 ] || exit 1
printf '%s\n' "${CHROME_TEST_LISTENERS:-p123
n127.0.0.1:9222}"
STUB
chmod +x "$trial/bin/uname" "$trial/bin/pgrep" "$trial/bin/open" "$trial/bin/lsof"
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
  connect_before_launch=0
  [[ "$state" != closed ]] || connect_before_launch=1
  CHROME_TEST_CONNECT_BEFORE_LAUNCH="$connect_before_launch" CHROME_TEST_PROCESS="$state" "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error"
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
CHROME_TEST_CONNECT_BEFORE_LAUNCH=1 CHROME_TEST_PROCESS=closed CHROME_TEST_LAUNCH_FAIL=1 "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error" || result=$?
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
  local connect_before_launch=0
  [[ "$should_launch" != yes ]] || connect_before_launch=1
  output="$(CHROME_TEST_CONNECT_BEFORE_LAUNCH="$connect_before_launch" CHROME_TEST_PROCESS=closed "$entrypoint" "$@")"
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
  --restore-check-fn --namespace --headers --executable-path --cdp --cdp-headers \
  --extension --init-script --enable --profile --state --proxy --proxy-bypass \
  --args --user-agent -p --provider --device --session-name --color-scheme \
  --download-path --max-output --allowed-domains --capture --action-policy \
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
  assert_launch_behavior no --debug false --max-output 100 "$command" --help
done
assert_launch_behavior browserless connect 9222
output="$(CHROME_TEST_PROCESS=running "$entrypoint" connect 9222)"
[[ "$output" == "$(printf '%s\n' --session dotfiles-chrome --pin-tab connect 9222)" ]]
assert_launch_behavior browserless --json connect ws://example.invalid/devtools/browser/test
assert_launch_behavior yes fill '#input' -- --help
assert_launch_behavior yes --user-agent --help snapshot
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
rm -f "$CHROME_TEST_LAUNCH" "$CHROME_TEST_STDIN_COPY.before" "$CHROME_TEST_STDIN_COPY.after"
printf 'console.log("fixture");\n\n' > "$trial/eval-input"
CHROME_TEST_CONNECT_BEFORE_LAUNCH=1 CHROME_TEST_PROCESS=closed CHROME_TEST_COPY_STDIN=1 "$entrypoint" eval --stdin < "$trial/eval-input" > "$trial/eval-output"
cmp "$trial/eval-input" "$CHROME_TEST_STDIN_COPY.before"
cmp "$trial/eval-input" "$CHROME_TEST_STDIN_COPY.after"
[[ "$(cat "$trial/eval-output")" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab eval --stdin)" ]]
assert_launch_behavior no --json false
assert_launch_behavior no --restore skills get core
assert_launch_behavior no --restore example-key skills get core
assert_launch_behavior no --restore=example-key skills get core
assert_launch_behavior no --unknown-future-option skills get core
rm -f "$CHROME_TEST_LAUNCH"
CHROME_TEST_OS=Linux CHROME_TEST_PROCESS=closed "$entrypoint" tab list >/dev/null
test ! -f "$CHROME_TEST_LAUNCH"

# Known JSON/plain/colored diagnostics recover without leaking a first response.
for json_shape in 1 2 3 4 5 6 7; do
  rm -f "$CHROME_TEST_LAUNCH"
  arguments=(tab list)
  if [[ "$json_shape" -le 2 || "$json_shape" == 6 ]]; then arguments=(--json tab list); fi
  output="$(CHROME_TEST_JSON_DISCOVERY="$json_shape" CHROME_TEST_CONNECT_BEFORE_LAUNCH=1 CHROME_TEST_PROCESS=closed "$entrypoint" "${arguments[@]}")"
  [[ "$output" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab "${arguments[@]}")" ]]
  test -f "$CHROME_TEST_LAUNCH"
done

# Action errors, including quoted discovery words, must not trigger a retry.
for error in 'selector was not found' 'Evaluation failed: No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp.'; do
  rm -f "$CHROME_TEST_LAUNCH"
  result=0
  CHROME_TEST_PROCESS=closed BROWSER_TEST_EXIT=1 BROWSER_TEST_ERROR="$error" "$entrypoint" click '@e1' > "$trial/attempt" 2> "$trial/error" || result=$?
  [[ "$result" == 1 ]]
  [[ "$(cat "$trial/error")" == "$error" ]]
  [[ "$(cat "$trial/attempt")" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab click '@e1')" ]]
  test ! -f "$CHROME_TEST_LAUNCH"
done

rm -f "$CHROME_TEST_LAUNCH"
json_error='{"success":false,"error":"action failed","data":{"error":"No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp."}}'
result=0
CHROME_TEST_PROCESS=closed BROWSER_TEST_JSON_ERROR="$json_error" "$entrypoint" --json eval example > "$trial/attempt" || result=$?
[[ "$result" == 1 ]]
[[ "$(cat "$trial/attempt")" == "$json_error" ]]
test ! -f "$CHROME_TEST_LAUNCH"
# Help must reach the CLI without buffering stdin or launching Chrome.
CHROME_TEST_PROCESS=closed "$entrypoint" eval --stdin --help < "$trial/eval-input" > "$trial/attempt"
[[ "$(cat "$trial/attempt")" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab eval --stdin --help)" ]]
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
CHROME_TEST_CONNECT_BEFORE_LAUNCH=1 CHROME_TEST_PROCESS=never "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error" || result=$?
[[ "$result" == 1 ]]
test ! -s "$trial/attempt"
[[ "$(cat "$trial/error")" == *'did not become observable'* ]]
[[ "$(wc -l < "$CHROME_TEST_WAIT" | tr -d ' ')" == 10 ]]
rm -f "$CHROME_TEST_LAUNCH" "$CHROME_TEST_WAIT"
CHROME_TEST_CONNECT_BEFORE_LAUNCH=1 CHROME_TEST_PROCESS=final-wait "$entrypoint" tab list > "$trial/attempt"
[[ "$(wc -l < "$CHROME_TEST_WAIT" | tr -d ' ')" == 10 ]]
[[ "$(cat "$trial/attempt")" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab tab list)" ]]
rm -f "$CHROME_TEST_LAUNCH"
CHROME_TEST_CONNECT_BEFORE_LAUNCH=1 CHROME_TEST_PROCESS=closed-denied "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error"
[[ "$(cat "$trial/error")" == *'browser state unknown'* ]]
[[ "$(cat "$trial/attempt")" == "$(printf '%s\n' --session dotfiles-chrome --auto-connect --pin-tab tab list)" ]]
echo 'Chrome entrypoint: closed launched, running reused, denied distinguished, launch failure bounded'

# Running Chrome: auto-discovery fails, explicit connect succeeds, tabs verify.
export CHROME_TEST_TRACE="$trial/direct-trace"
export CHROME_TEST_CONNECTED="$trial/connected"
export CHROME_TEST_LSOF_ARGS="$trial/lsof-args"
export CHROME_TEST_DIRECT=1
for args in plain json snapshot; do
  rm -f "$HOME/Library/Caches/agent-chrome/connection.json" "$CHROME_TEST_TRACE" "$CHROME_TEST_CONNECTED" "$CHROME_TEST_LAUNCH"
  arguments=(tab list)
  [[ "$args" != json ]] || arguments=(--json tab list)
  [[ "$args" != snapshot ]] || arguments=(snapshot)
  output="$("$entrypoint" "${arguments[@]}" 2> "$trial/error")" || { cat "$trial/error" >&2; exit 1; }
  [[ "$output" == "$(printf '%s\n' --session dotfiles-chrome --pin-tab "${arguments[@]}")" ]]
  expected_calls=4
  [[ "$args" != plain ]] || expected_calls=3
  [[ "$(wc -l < "$CHROME_TEST_TRACE")" -eq "$expected_calls" ]]
  [[ "$(sed -n '2p' "$CHROME_TEST_TRACE")" == '--session dotfiles-chrome --pin-tab connect 9222' ]]
  [[ "$(sed -n '3p' "$CHROME_TEST_TRACE")" == '--session dotfiles-chrome --pin-tab tab list' ]]
  [[ "$(cat "$CHROME_TEST_LSOF_ARGS")" == '-nP -a -c /^Google Chrome$/ -iTCP -sTCP:LISTEN -Fn' ]]
  test ! -f "$CHROME_TEST_LAUNCH"
done
# A fresh process opens a task tab using exactly the verified connection mode.
: > "$CHROME_TEST_TRACE"
output="$(cd "$trial/other-project" && "$entrypoint" tab new https://example.org)"
[[ "$output" == "$(printf '%s\n' --session dotfiles-chrome --cdp 9222 --pin-tab tab new https://example.org)" ]]
[[ "$(wc -l < "$CHROME_TEST_TRACE" | tr -d ' ')" == 1 ]]
# An additional listener does not invalidate the verified process/port pair.
: > "$CHROME_TEST_TRACE"
CHROME_TEST_LISTENERS=$'p321\nn127.0.0.1:9333\np123\nn127.0.0.1:9222' "$entrypoint" tab list >/dev/null
[[ "$(cat "$CHROME_TEST_TRACE")" == '--session dotfiles-chrome --cdp 9222 --pin-tab tab list' ]]
# Interactive chat inherits stdin and uses the verified connection too.
printf 'interactive-input' | CHROME_TEST_COPY_STDIN=1 CHROME_TEST_STDIN_COPY="$trial/chat-input" "$entrypoint" chat > "$trial/chat-command"
[[ "$(cat "$trial/chat-input")" == interactive-input ]]
[[ "$(cat "$trial/chat-command")" == "$(printf '%s\n' --session dotfiles-chrome --cdp 9222 --pin-tab chat)" ]]
# Never replay a potentially mutating action, even after successful recovery.
for action in click fill eval; do
  rm -f "$HOME/Library/Caches/agent-chrome/connection.json" "$CHROME_TEST_TRACE" "$CHROME_TEST_CONNECTED"
  result=0
  "$entrypoint" "$action" fixture > "$trial/attempt" 2> "$trial/error" || result=$?
  [[ "$result" == 1 ]]
  [[ "$(wc -l < "$CHROME_TEST_TRACE" | tr -d ' ')" == 3 ]]
  [[ "$(cat "$trial/error")" == *'fresh snapshot before continuing'* ]]
  test -f "$CHROME_TEST_CONNECTED"
done
# Only a unique Chrome-owned loopback port is eligible. No HTTP probe needed.
for listeners in 'n0.0.0.0:9222' 'n*:9222' 'n192.168.1.10:9222' $'n127.0.0.1:9222\nn127.0.0.1:9333' 'n127.0.0.1:70000'; do
  rm -f "$HOME/Library/Caches/agent-chrome/connection.json" "$CHROME_TEST_TRACE" "$CHROME_TEST_CONNECTED"
  result=0
  CHROME_TEST_LISTENERS="$(printf 'p123\n%s' "$listeners")" "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error" || result=$?
  [[ "$result" == 1 ]]
  [[ "$(wc -l < "$CHROME_TEST_TRACE" | tr -d ' ')" == 1 ]]
  test ! -f "$CHROME_TEST_CONNECTED"
done
for failure in CHROME_TEST_LSOF_FAIL CHROME_TEST_CONNECT_FAIL CHROME_TEST_VERIFY_FAIL; do
  rm -f "$HOME/Library/Caches/agent-chrome/connection.json" "$CHROME_TEST_TRACE" "$CHROME_TEST_CONNECTED"
  result=0
  env "$failure=1" "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error" || result=$?
  [[ "$result" == 1 ]]
  test ! -f "$CHROME_TEST_LAUNCH"
done
for listeners in 'n[::1]:9333' $'n127.0.0.1:9222\nn[::1]:9222'; do
  rm -f "$HOME/Library/Caches/agent-chrome/connection.json" "$CHROME_TEST_TRACE" "$CHROME_TEST_CONNECTED"
  CHROME_TEST_LISTENERS="$(printf 'p123\n%s' "$listeners")" "$entrypoint" tab list > "$trial/attempt" 2> "$trial/error"
  [[ "$(wc -l < "$CHROME_TEST_TRACE" | tr -d ' ')" == 3 ]]
done
rm -f "$HOME/Library/Caches/agent-chrome/connection.json" "$CHROME_TEST_CONNECTED"
: > "$CHROME_TEST_TRACE"
if CHROME_TEST_CONNECT_FAIL=1 "$entrypoint" tab list > /dev/null 2>&1; then exit 1; fi
before="$(wc -l < "$CHROME_TEST_TRACE")"
if "$entrypoint" connect 9222 >/dev/null 2>&1; then exit 1; fi
if "$entrypoint" chat </dev/null >/dev/null 2>&1; then exit 1; fi
if (cd "$trial/other-project" && "$entrypoint" tab new https://example.org) > /dev/null 2> "$trial/error"; then exit 1; fi
[[ "$(wc -l < "$CHROME_TEST_TRACE")" == "$before" ]]
[[ "$(cat "$trial/error")" == *'awaiting confirmation'* ]]
AGENT_CHROME_RETRY_AFTER_APPROVAL=1 "$entrypoint" tab list >/dev/null
# Page-level timeouts must leave the browser usable in the next chat.
if BROWSER_TEST_EXIT=1 BROWSER_TEST_ERROR='Wait timed out after 1000ms' "$entrypoint" wait example >/dev/null 2>&1; then exit 1; fi
"$entrypoint" tab list >/dev/null
# Two callers arriving together may perform only one cold recovery.
rm -f "$HOME/Library/Caches/agent-chrome/connection.json" "$CHROME_TEST_CONNECTED"
: > "$CHROME_TEST_TRACE"
"$entrypoint" tab list >/dev/null 2>"$trial/first" &
first=$!
(cd "$trial/other-project" && "$entrypoint" tab list >/dev/null 2>"$trial/second") &
second=$!
wait "$first"
wait "$second"
[[ "$(grep -c ' connect ' "$CHROME_TEST_TRACE")" == 1 ]]
[[ "$(grep -c -- '--auto-connect' "$CHROME_TEST_TRACE")" == 1 ]]
unset CHROME_TEST_DIRECT
printf '%s\n' 'Chrome direct recovery: verified connection, safe reads, no write replay, ambiguous/remote ports rejected'
