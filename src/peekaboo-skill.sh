#!/bin/bash
# Install the official, checksum-pinned Peekaboo skill without claiming or
# overwriting independently managed skills.

ensure_peekaboo_skill() {
  local url="$1" expected_sha256="$2"
  local skill_dir="$HOME/.agents/skills/peekaboo"
  local skill_file="$skill_dir/SKILL.md"
  local marker="$HOME/Library/Application Support/dotfiles/peekaboo-skill.sha256"
  local claude_skill="$HOME/.claude/skills/peekaboo"
  local claude_target="../../.agents/skills/peekaboo"
  local current_sha256 previous_sha256 temporary download_sha256

  if [[ -L "$skill_dir" || ( -e "$skill_dir" && ! -d "$skill_dir" ) || -L "$skill_file" ]]; then
    printf 'Peekaboo skill: existing path is not a managed directory/file: %s\n' "$skill_dir" >&2
    return 1
  fi
  if [[ -d "$skill_dir" && ! -f "$skill_file" && -n "$(ls -A "$skill_dir")" ]]; then
    printf 'Peekaboo skill: refusing to take over nonempty directory: %s\n' "$skill_dir" >&2
    return 1
  fi
  if [[ -L "$claude_skill" ]]; then
    case "$(readlink "$claude_skill")" in
      "$claude_target"|"$skill_dir") ;;
      *) printf 'Peekaboo skill: refusing to replace existing Claude skill link: %s\n' "$claude_skill" >&2; return 1 ;;
    esac
  elif [[ -e "$claude_skill" ]]; then
    printf 'Peekaboo skill: refusing to replace existing Claude skill: %s\n' "$claude_skill" >&2
    return 1
  fi

  previous_sha256="$(cat "$marker" 2>/dev/null || true)"
  current_sha256=""
  if [[ -f "$skill_file" ]]; then
    current_sha256="$(shasum -a 256 "$skill_file" | awk '{print $1}')"
    if [[ "$current_sha256" != "$expected_sha256" && "$current_sha256" != "$previous_sha256" ]]; then
      printf 'Peekaboo skill: refusing to overwrite unrecognized or locally modified SKILL.md\n' >&2
      return 1
    fi
  fi

  if [[ "$current_sha256" != "$expected_sha256" ]]; then
    mkdir -p "$skill_dir"
    temporary="$(mktemp "$skill_dir/.SKILL.md.XXXXXXXX")"
    if ! curl --fail --location --silent --show-error --max-time 30 \
      --output "$temporary" "$url"; then
      rm -f "$temporary"
      printf 'Peekaboo skill: upstream download failed; previous installation preserved.\n' >&2
      return 1
    fi
    download_sha256="$(shasum -a 256 "$temporary" | awk '{print $1}')"
    if [[ "$download_sha256" != "$expected_sha256" ]]; then
      rm -f "$temporary"
      printf 'Peekaboo skill: upstream checksum mismatch; refusing installation.\n' >&2
      return 1
    fi
    chmod 644 "$temporary"
    mv "$temporary" "$skill_file"
  fi

  mkdir -p "$(dirname "$marker")" "$(dirname "$claude_skill")"
  temporary="$(mktemp "$marker.XXXXXXXX")"
  printf '%s\n' "$expected_sha256" > "$temporary"
  mv "$temporary" "$marker"
  if [[ ! -L "$claude_skill" ]]; then
    ln -s "$claude_target" "$claude_skill"
  fi
}
