#!/bin/bash
set -euo pipefail
[[ "${RUN_COMPUTER_USE_E2E:-0}" == 1 ]] || exit 0
[[ "$(uname -s)" == Darwin ]] || exit 1
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
trial="$(mktemp -d /tmp/browser-use-e2e.XXXXXXXX)"
export HOME="$trial/home" CODEX_HOME="$trial/home/.codex"
export npm_config_prefix="$trial/npm" npm_config_cache="$trial/npm-cache"
export UV_TOOL_DIR="$trial/tools" UV_TOOL_BIN_DIR="$HOME/.local/bin"
export BH_RUNTIME_DIR="$trial/run" BH_HOME="$trial/harness" BH_TELEMETRY=0
unset BU_CDP_URL BU_CDP_WS BU_NAME BU_AUTOSPAWN BROWSER_USE_API_KEY BH_REQUIRE_EXISTING_DAEMON
export PATH="$HOME/.local/bin:$npm_config_prefix/bin:$PATH"
chrome_pid=
cleanup() {
  if [[ -n "$chrome_pid" ]]; then
    browser-use --reload >/dev/null 2>&1 || true
    kill "$chrome_pid" 2>/dev/null || true
    wait "$chrome_pid" 2>/dev/null || true
  fi
  # Chrome helpers can finish writing profile files after the parent exits.
  for _ in {1..5}; do
    if rm -rf "$trial" 2>/dev/null; then return 0; fi
    sleep 1
  done
  rm -rf "$trial"
}
trap cleanup EXIT
mkdir -p "$HOME/.agents/skills/agent-browser" "$CODEX_HOME/skills" "$trial/run"
echo local-customization > "$HOME/.agents/skills/agent-browser/SKILL.md"
ln -s "$HOME/.agents/skills/agent-browser" "$CODEX_HOME/skills/agent-browser"
printf '%s\n' '{"version":3,"skills":{"agent-browser":{"source":"vercel-labs/agent-browser"}}}' > "$HOME/.agents/.skill-lock.json"
npm install --global skills
for hook in run_after_40-ensure-peekaboo-skill.sh run_after_50-ensure-browser-use.sh; do
  chezmoi --source "$repo_root/home" execute-template --file "$repo_root/home/$hook.tmpl" > "$trial/$hook"
  bash "$trial/$hook"
done
bash "$trial/run_after_50-ensure-browser-use.sh"
[[ -s "$HOME/.agents/skills/peekaboo/SKILL.md" && ! -e "$HOME/.agents/skills/agent-browser" ]]
[[ ! -L "$CODEX_HOME/skills/agent-browser" ]]
node -e 'const {skills}=require(process.argv[1]); if(skills["agent-browser"] || !skills.peekaboo)process.exit(1)' "$HOME/.agents/.skill-lock.json"
archives=("$HOME/Library/Application Support/dotfiles/retired-skills"/agent-browser-*)
[[ "${#archives[@]}" == 1 && "$(cat "${archives[0]}/agents/SKILL.md")" == local-customization ]]
[[ "$(command -v browser-use)" == "$HOME/.local/bin/browser-use" ]]
browser-use skill show > "$trial/skill"
grep -q 'list_tabs' "$trial/skill"
peekaboo --version >/dev/null

# Only the fixture browser writes a discovery file inside this disposable HOME.
profile="$HOME/Library/Application Support/Google/Chrome"
mkdir -p "$profile"
page="file://$trial/fixture.html"
echo '<title>Browser Use fixture</title><button onclick="document.title=String(++window.count)">Update</button><script>window.count=0</script>' > "$trial/fixture.html"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-first-run \
  --user-data-dir="$profile" --remote-debugging-port=0 "$page" >"$trial/chrome.log" 2>&1 &
chrome_pid=$!
for _ in {1..100}; do [[ -s "$profile/DevToolsActivePort" ]] && break; sleep 0.1; done
[[ -s "$profile/DevToolsActivePort" ]]
export FIXTURE_URL="$page"
cd "$trial"
browser-use <<'PY'
import os
from browser_harness.admin import daemon_browser_kind
assert daemon_browser_kind(NAME) == 'local'
target = next(tab for tab in list_tabs() if tab.get('url') == os.environ['FIXTURE_URL'])
switch_tab(target['targetId'])
js("document.querySelector('button').click()")
PY
cd "$HOME"
browser-use <<'PY'
import os
from browser_harness.admin import daemon_browser_kind
assert daemon_browser_kind(NAME) == 'local'
assert page_info()['url'] == os.environ['FIXTURE_URL']
assert js("document.title") == '1'
PY
echo 'Browser Use migrated the old skill and reused the same live page across two CLI processes.'
