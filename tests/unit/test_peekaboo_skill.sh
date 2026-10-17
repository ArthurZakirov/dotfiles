#!/bin/bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$repo_root/src/peekaboo-skill.sh"

test_home="$(mktemp -d)"
HOME="$test_home"
export HOME
trap 'rm -rf "$test_home"' EXIT
url="https://example.invalid/peekaboo/SKILL.md"
payload="official upstream skill v1"
digest="$(printf '%s' "$payload" | shasum -a 256 | awk '{print $1}')"
curl_calls=0
curl() {
  local output=""
  while (($#)); do
    if [[ "$1" == --output ]]; then
      output="$2"
      shift 2
    else
      shift
    fi
  done
  ((curl_calls += 1))
  [[ "${curl_fail:-0}" == 0 ]] || return 22
  printf '%s' "$payload" > "$output"
}
skill="$HOME/.agents/skills/peekaboo/SKILL.md"
link="$HOME/.claude/skills/peekaboo"
marker="$HOME/Library/Caches/chezmoi/peekaboo-skill.sha256"

# New installation and idempotent repeat (without network).
ensure_peekaboo_skill "$url" "$digest"
[[ "$(cat "$skill")" == "$payload" ]]
[[ -L "$link" && "$(readlink "$link")" == '../../.agents/skills/peekaboo' ]]
[[ "$(cat "$marker")" == "$digest" ]]
ensure_peekaboo_skill "$url" "$digest"
[[ "$curl_calls" == 1 ]]

# Failed download and integrity mismatch preserve the installed version.
next_payload="official upstream skill v2"
next_digest="$(printf '%s' "$next_payload" | shasum -a 256 | awk '{print $1}')"
curl_fail=1
if ensure_peekaboo_skill "$url" "$next_digest" 2>/dev/null; then exit 1; fi
[[ "$(cat "$skill")" == "$payload" ]]
curl_fail=0
if ensure_peekaboo_skill "$url" "$next_digest" 2>/dev/null; then exit 1; fi
[[ "$(cat "$skill")" == "$payload" ]]

# A version bump replaces only a previously managed, unmodified skill.
payload="$next_payload"
ensure_peekaboo_skill "$url" "$next_digest"
[[ "$(cat "$skill")" == "$next_payload" ]]
[[ "$(cat "$marker")" == "$next_digest" ]]

# Local modifications are protected even after a version bump.
printf 'local override' > "$skill"
if ensure_peekaboo_skill "$url" "$digest" 2>/dev/null; then exit 1; fi
[[ "$(cat "$skill")" == "local override" ]]

# Existing independently owned Claude skill must never be replaced.
rm -rf "$test_home"
mkdir -p "$HOME/.claude/skills"
printf 'existing skill' > "$link"
if ensure_peekaboo_skill "$url" "$digest" 2>/dev/null; then exit 1; fi
[[ "$(cat "$link")" == "existing skill" ]]
[[ ! -e "$HOME/.agents/skills/peekaboo/SKILL.md" ]]

# An independently managed .agents/skills/peekaboo symlink must be preserved.
rm -f "$link"
mkdir -p "$HOME/.agents/skills"
ln -s /tmp/preexisting-peekaboo "$HOME/.agents/skills/peekaboo"
if ensure_peekaboo_skill "$url" "$digest" 2>/dev/null; then exit 1; fi
[[ "$(readlink "$HOME/.agents/skills/peekaboo")" == /tmp/preexisting-peekaboo ]]

echo 'peekaboo skill: fresh install, idempotency, recovery, upgrade, and conflict protection passed'
