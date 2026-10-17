#!/bin/bash
set -euo pipefail

if [[ "${RUN_COMPUTER_USE_E2E:-0}" != 1 ]]; then
  echo 'Real computer-use integration skipped (set RUN_COMPUTER_USE_E2E=1).'
  exit 0
fi
[[ "$(uname -s)" == Darwin ]] || { echo 'Real computer-use integration requires macOS.' >&2; exit 1; }
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
trial="$(mktemp -d)"
cleanup() {
  "$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e close >/dev/null 2>&1 || true
  rm -rf "$trial"
}
trap cleanup EXIT
export HOME="$trial/home"
export npm_config_prefix="$trial/npm"
export npm_config_cache="$trial/npm-cache"
mkdir -p "$HOME" "$npm_config_prefix/bin"
export PATH="$npm_config_prefix/bin:$PATH"

command -v peekaboo >/dev/null
command -v chezmoi >/dev/null
command -v npm >/dev/null
command -v npx >/dev/null

# The actual missing-CLI installer is exercised on CI's fresh Mac. On a
# developer Mac with an existing agent-browser, force an isolated npm install.
source "$repo_root/src/apps.sh"
if command -v agent-browser >/dev/null 2>&1; then
  npm install --global agent-browser
else
  install_agent_browser_cli
fi
[[ -x "$npm_config_prefix/bin/agent-browser" ]]
"$npm_config_prefix/bin/agent-browser" --version

# The standalone Vercel skills CLI must also survive fresh setup.
if command -v skills >/dev/null 2>&1; then
  npm install --global skills
else
  install_skills_cli
fi
[[ -x "$npm_config_prefix/bin/skills" ]]
"$npm_config_prefix/bin/skills" --version
npx --no-install skills --version

# Render and exercise the exact chezmoi hooks with the disposable HOME.
for hook in run_after_40-ensure-peekaboo-skill.sh.tmpl run_after_50-ensure-agent-browser.sh.tmpl; do
  rendered="$trial/${hook%.tmpl}"
  chezmoi --source "$repo_root/home" execute-template --file "$repo_root/home/$hook" > "$rendered"
  /bin/bash "$rendered"
done

[[ -s "$HOME/.agents/skills/peekaboo/SKILL.md" ]]
[[ -f "$HOME/.claude/skills/peekaboo/SKILL.md" ]]
[[ -s "$HOME/.agents/skills/agent-browser/SKILL.md" ]]
[[ -f "$HOME/.claude/skills/agent-browser/SKILL.md" ]]
"$npm_config_prefix/bin/skills" list -g --json | grep -q 'agent-browser'
node -e '
  const lock=require(process.argv[1]);
  if(lock.skills?.["agent-browser"]?.source!=="vercel-labs/agent-browser")process.exit(1)
' "$HOME/.agents/.skill-lock.json"
"$npm_config_prefix/bin/agent-browser" skills get core >/dev/null
"$npm_config_prefix/bin/agent-browser" skills get electron >/dev/null
peekaboo --version >/dev/null

# Real browser runtime and UI action, with no network services or personal profile.
"$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e open 'data:text/html,<button onclick="this.textContent=%27clicked%27">click me</button>'
"$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e snapshot | grep -q 'click me'
"$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e click 'button'
"$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e snapshot | grep -q 'clicked'
"$npm_config_prefix/bin/agent-browser" --session dotfiles-e2e close

# Repeated apply must not duplicate skills or damage the browser runtime.
/bin/bash "$trial/run_after_40-ensure-peekaboo-skill.sh"
/bin/bash "$trial/run_after_50-ensure-agent-browser.sh"
[[ -f "$HOME/.claude/skills/agent-browser/SKILL.md" ]]
[[ -f "$HOME/.claude/skills/peekaboo/SKILL.md" ]]
echo 'Real macOS computer-use E2E passed: CLIs, skills, Chromium, click, snapshot, repeated apply.'
