#!/bin/bash
# Install Vercel's global Agent Browser skill with its managed skills CLI.
# An existing installation belongs to its original owner; never overwrite it.

ensure_agent_browser_skill() {
  local skill_dir="$HOME/.agents/skills/agent-browser"
  local skill_file="$skill_dir/SKILL.md"
  local metadata="$HOME/.agents/.skill-lock.json"
  local claude_skill="$HOME/.claude/skills/agent-browser"
  local marker="$HOME/Library/Application Support/dotfiles/agent-browser-skill.sha256"
  local installed_digest previously_managed_digest

  if [[ -L "$skill_dir" || ( -e "$skill_dir" && ! -d "$skill_dir" ) ]]; then
    printf 'Agent Browser: existing canonical skill path is not a directory: %s\n' "$skill_dir" >&2
    return 1
  fi
  if [[ -d "$skill_dir" ]]; then
    if [[ ! -f "$skill_file" ]] || ! node -e '
      const lock = require(process.argv[1]);
      process.exit(lock.skills?.["agent-browser"]?.source === "vercel-labs/agent-browser" ? 0 : 1);
    ' "$metadata" 2>/dev/null; then
      printf 'Agent Browser: refusing to overwrite a skill not owned by Vercel npx skills: %s\n' "$skill_dir" >&2
      return 1
    fi
    installed_digest="$(shasum -a 256 "$skill_file" | awk '{print $1}')"
    previously_managed_digest="$(cat "$marker" 2>/dev/null || true)"
    if [[ -n "$previously_managed_digest" && "$installed_digest" != "$previously_managed_digest" ]]; then
      printf 'Agent Browser: existing Vercel skill was modified locally; refusing to claim it.\n' >&2
      return 1
    fi
    if [[ -L "$claude_skill" ]]; then
      if [[ ! "$claude_skill" -ef "$skill_dir" ]]; then
        printf 'Agent Browser: Claude skill link targets another installation: %s\n' "$claude_skill" >&2
        return 1
      fi
    elif [[ -e "$claude_skill" ]]; then
      printf 'Agent Browser: refusing to overwrite existing Claude skill: %s\n' "$claude_skill" >&2
      return 1
    else
      mkdir -p "$(dirname "$claude_skill")"
      ln -s '../../.agents/skills/agent-browser' "$claude_skill"
    fi
    mkdir -p "$(dirname "$marker")"
    printf '%s\n' "$installed_digest" > "$marker"
    return 0
  fi

  if [[ -e "$claude_skill" || -L "$claude_skill" ]]; then
    printf 'Agent Browser: refusing to overwrite an existing Claude skill: %s\n' "$claude_skill" >&2
    return 1
  fi

  skills add vercel-labs/agent-browser \
    --global --agent codex claude-code --skill agent-browser --yes --json || return 1
  [[ -f "$skill_file" && -f "$claude_skill/SKILL.md" ]] || {
    printf 'Agent Browser: npx skills returned without usable Codex and Claude installations.\n' >&2
    return 1
  }
  mkdir -p "$(dirname "$marker")"
  shasum -a 256 "$skill_file" | awk '{print $1}' > "$marker"
}
