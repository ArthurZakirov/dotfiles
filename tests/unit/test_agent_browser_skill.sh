#!/bin/bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)/src/agent-browser-skill.sh"

sandbox="$(mktemp -d)"
trap 'rm -rf "$sandbox"' EXIT
export HOME="$sandbox/home"
mkdir -p "$HOME"
skills_calls=0
skills() {
  ((skills_calls += 1))
  [[ "$*" == 'add vercel-labs/agent-browser --global --agent codex claude-code --skill agent-browser --yes --json' ]]
  [[ "${skills_fail:-0}" == 0 ]] || return 17
  mkdir -p "$HOME/.agents/skills/agent-browser" "$HOME/.claude/skills"
  printf 'Vercel skill' > "$HOME/.agents/skills/agent-browser/SKILL.md"
  printf '%s\n' '{"version":3,"skills":{"agent-browser":{"source":"vercel-labs/agent-browser"}}}' > "$HOME/.agents/.skill-lock.json"
  ln -s '../../.agents/skills/agent-browser' "$HOME/.claude/skills/agent-browser"
}

# New install reaches the upstream installer, with agent/scope selection explicit.
ensure_agent_browser_skill
[[ "$skills_calls" == 1 ]]
[[ -f "$HOME/.claude/skills/agent-browser/SKILL.md" ]]
# Repeat is a true no-op: npx skills add would overwrite a prior install.
ensure_agent_browser_skill
[[ "$skills_calls" == 1 ]]
# Missing Claude link is repaired without rewriting canonical Vercel skill.
rm "$HOME/.claude/skills/agent-browser"
ensure_agent_browser_skill
[[ "$skills_calls" == 1 ]]
[[ -f "$HOME/.claude/skills/agent-browser/SKILL.md" ]]

# A previously installed Vercel skill edited locally is preserved.
printf 'local changes' > "$HOME/.agents/skills/agent-browser/SKILL.md"
if ensure_agent_browser_skill 2>/dev/null; then exit 1; fi
[[ "$skills_calls" == 1 ]]

# A skill without Vercel's upstream provenance must not be adopted.
rm -rf "$HOME/.agents/skills/agent-browser" "$HOME/.claude/skills/agent-browser"
mkdir -p "$HOME/.agents/skills/agent-browser"
printf 'unrelated skill' > "$HOME/.agents/skills/agent-browser/SKILL.md"
rm "$HOME/.agents/.skill-lock.json"
if ensure_agent_browser_skill 2>/dev/null; then exit 1; fi
[[ "$(cat "$HOME/.agents/skills/agent-browser/SKILL.md")" == 'unrelated skill' ]]
[[ "$skills_calls" == 1 ]]

# An independently owned Claude skill also blocks initial installation.
rm -rf "$HOME/.agents/skills/agent-browser"
mkdir -p "$HOME/.claude/skills/agent-browser"
printf 'other' > "$HOME/.claude/skills/agent-browser/SKILL.md"
if ensure_agent_browser_skill 2>/dev/null; then exit 1; fi
[[ "$skills_calls" == 1 ]]
[[ ! -e "$HOME/.agents/skills/agent-browser" ]]

# After a transient installer failure, the next apply retries.
rm -rf "$HOME/.claude/skills/agent-browser"
skills_fail=1
if ensure_agent_browser_skill 2>/dev/null; then exit 1; fi
[[ "$skills_calls" == 2 ]]
[[ ! -e "$HOME/.agents/skills/agent-browser" ]]
skills_fail=0
ensure_agent_browser_skill
[[ "$skills_calls" == 3 ]]
[[ -f "$HOME/.agents/skills/agent-browser/SKILL.md" ]]

echo 'agent-browser skill: install, repeat, link repair, collision protection and retry passed'
