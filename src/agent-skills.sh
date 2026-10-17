#!/bin/bash
# Install only canonical global .agents/skills through Vercel's skills CLI.
# Independently installed or locally modified skills must never be overwritten.

ensure_agent_skill() {
  local name="$1" source="$2"
  local directory="$HOME/.agents/skills/$name"
  local file="$directory/SKILL.md"
  local lock="$HOME/.agents/.skill-lock.json"
  local marker="$HOME/Library/Application Support/dotfiles/$name-skill.sha256"
  local previous_digest="" current_digest="" temporary

  if [[ -L "$directory" || ( -e "$directory" && ! -d "$directory" ) || -L "$file" ]]; then
    printf 'Agent skill: refusing to replace a non-directory or symlink: %s\n' "$directory" >&2
    return 1
  fi
  if [[ -e "$directory" ]]; then
    if [[ ! -f "$file" ]] || ! node -e '
      const [lockPath, name, expectedSource] = process.argv.slice(1);
      const lock = require(lockPath);
      process.exit(lock.skills?.[name]?.source === expectedSource ? 0 : 1);
    ' "$lock" "$name" "$source" 2>/dev/null; then
      printf 'Agent skill: refusing to adopt unrecognized installation: %s\n' "$directory" >&2
      return 1
    fi
    current_digest="$(shasum -a 256 "$file" | awk '{print $1}')"
    previous_digest="$(cat "$marker" 2>/dev/null || true)"
    if [[ -n "$previous_digest" && "$current_digest" != "$previous_digest" ]]; then
      printf 'Agent skill: local content changed; review before reconciling %s\n' "$name" >&2
      return 1
    fi
  else
    npx --no-install skills add "$source" \
      --global --agent codex --skill "$name" --yes --json || return 1
    if [[ ! -f "$file" ]] || ! node -e '
      const [lockPath, name, expectedSource] = process.argv.slice(1);
      const lock = require(lockPath);
      process.exit(lock.skills?.[name]?.source === expectedSource ? 0 : 1);
    ' "$lock" "$name" "$source" 2>/dev/null; then
      printf 'Agent skill: installer did not create a verified %s skill\n' "$name" >&2
      return 1
    fi
    current_digest="$(shasum -a 256 "$file" | awk '{print $1}')"
  fi

  mkdir -p "$(dirname "$marker")"
  temporary="$(mktemp "$marker.XXXXXXXX")"
  printf '%s\n' "$current_digest" > "$temporary"
  mv "$temporary" "$marker"
}
