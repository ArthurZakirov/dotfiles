#!/bin/bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)/src/agent-skills.sh"

sandbox="$(mktemp -d)"
trap 'rm -rf "$sandbox"' EXIT
export HOME="$sandbox/home"
mkdir -p "$HOME"
install_calls=0
npx() {
  ((install_calls += 1))
  [[ "$1" == '--no-install' && "$2" == skills && "$3" == add ]]
  local source="$4" name="${9}"
  # Expected sequence: --no-install skills add SOURCE --global --agent codex --skill NAME --yes --json
  [[ "$5" == --global && "$6" == --agent && "$7" == codex && "$8" == --skill ]]
  [[ "${10}" == --yes && "${11}" == --json ]]
  [[ "${install_fail:-0}" == 0 ]] || return 17
  mkdir -p "$HOME/.agents/skills/$name"
  printf '%s\n' "official $name" > "$HOME/.agents/skills/$name/SKILL.md"
  node -e '
    const fs=require("fs"), path=require("path");
    const [file,name,source]=process.argv.slice(1);
    const lock=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,"utf8")):{version:3,skills:{}};
    lock.skills[name]={source};fs.writeFileSync(file,JSON.stringify(lock));
  ' "$HOME/.agents/.skill-lock.json" "$name" "$source"
}

# Install both skills through one CLI with only the selected Codex target.
ensure_agent_skill peekaboo openclaw/Peekaboo
ensure_agent_skill agent-browser vercel-labs/agent-browser
[[ "$install_calls" == 2 ]]
[[ -s "$HOME/.agents/skills/peekaboo/SKILL.md" ]]
[[ -s "$HOME/.agents/skills/agent-browser/SKILL.md" ]]
[[ ! -e "$HOME/.claude" ]]

# Reapplying performs no installation, preserves content, and does not claim
# modifications to a previous managed skill.
ensure_agent_skill peekaboo openclaw/Peekaboo
ensure_agent_skill agent-browser vercel-labs/agent-browser
[[ "$install_calls" == 2 ]]
printf 'local override' > "$HOME/.agents/skills/peekaboo/SKILL.md"
if ensure_agent_skill peekaboo openclaw/Peekaboo 2>/dev/null; then exit 1; fi
[[ "$(cat "$HOME/.agents/skills/peekaboo/SKILL.md")" == 'local override' ]]

# After a deliberate reviewed update, resetting the marker permits adoption.
rm "$HOME/Library/Application Support/dotfiles/peekaboo-skill.sha256"
ensure_agent_skill peekaboo openclaw/Peekaboo
[[ "$(cat "$HOME/Library/Application Support/dotfiles/peekaboo-skill.sha256")" == "$(printf 'local override' | shasum -a 256 | awk '{print $1}')" ]]
[[ "$install_calls" == 2 ]]

# Unknown provenance must never be adopted, even if the skill has the right name.
rm "$HOME/.agents/.skill-lock.json"
if ensure_agent_skill agent-browser vercel-labs/agent-browser 2>/dev/null; then exit 1; fi
[[ "$(cat "$HOME/.agents/skills/agent-browser/SKILL.md")" == 'official agent-browser' ]]

# An independently managed symlink must remain intact.
rm -rf "$HOME/.agents/skills/agent-browser"
ln -s /tmp/another-skill "$HOME/.agents/skills/agent-browser"
if ensure_agent_skill agent-browser vercel-labs/agent-browser 2>/dev/null; then exit 1; fi
[[ "$(readlink "$HOME/.agents/skills/agent-browser")" == /tmp/another-skill ]]

# A failed installer leaves a missing skill absent; a later apply can retry.
rm "$HOME/.agents/skills/agent-browser"
install_fail=1
if ensure_agent_skill agent-browser vercel-labs/agent-browser 2>/dev/null; then exit 1; fi
[[ "$install_calls" == 3 && ! -e "$HOME/.agents/skills/agent-browser" ]]
install_fail=0
ensure_agent_skill agent-browser vercel-labs/agent-browser
[[ "$install_calls" == 4 && -f "$HOME/.agents/skills/agent-browser/SKILL.md" ]]
[[ ! -e "$HOME/.claude" ]]

echo 'agent skills: Codex-only install, repeat, provenance, ownership, and retry passed'
