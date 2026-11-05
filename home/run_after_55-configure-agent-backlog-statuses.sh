#!/usr/bin/env bash
# Configure the existing Mac-wide board without changing tasks or user labels.
set -euo pipefail

board_root="${AGENT_BACKLOG_DIR:-$HOME/.local/share/agent-backlog}"
cli="$HOME/.local/bin/agent-backlog"
if [[ ! -x "$cli" ]]; then
  echo "Agent Backlog: CLI not yet provisioned; skipping status configuration." >&2
  exit 0
fi
# Ensure the Backlog.md project has been initialized before config discovery.
"$cli" config get statuses >/dev/null

/usr/bin/python3 - "$board_root" <<'PYCONFIG'
import ast
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

root = Path(sys.argv[1])
# Backlog.md resolves root config before either project-directory layout.
candidates = (
    root / "backlog.config.yml",
    root / "backlog" / "config.yml",
    root / ".backlog" / "config.yml",
)
config = next((path for path in candidates if path.is_file()), None)
if config is None:
    raise SystemExit("Agent Backlog: no active config found under " + str(root))

statuses = ("To Do", "In Progress", "Pushed", "PR", "Merged", "STG", "PRD", "Done")
confirmation_labels = ("✅ Reviewed", "✅ Behavior tested")
text = config.read_text()

def section(lines, key):
    """Locate a root-level YAML mapping entry, including its block value."""
    root_keys = []
    for number, line in enumerate(lines):
        match = re.match(r"^([A-Za-z_][\w-]*):(?:[ \t]|$)", line)
        if match:
            root_keys.append((number, match.group(1)))
    positions = [index for index, (line, name) in enumerate(root_keys) if name == key]
    if len(positions) > 1:
        raise SystemExit("Agent Backlog: duplicate " + key + " key in " + str(config))
    if not positions:
        return None
    position = positions[0]
    start = root_keys[position][0]
    end = root_keys[position + 1][0] if position + 1 < len(root_keys) else len(lines)
    return start, end

def set_statuses(content):
    lines = content.splitlines(keepends=True)
    replacement = "statuses: " + json.dumps(statuses, ensure_ascii=False) + "\n"
    bounds = section(lines, "statuses")
    if bounds is None:
        return content.rstrip("\n") + "\n" + replacement
    start, end = bounds
    # Consume the entire YAML node, not just its header: its old indented
    # '- status' lines would otherwise become invalid YAML under an inline list.
    old_block = lines[start + 1:end]
    trailing_comments = []
    for line in reversed(old_block):
        if not line.strip() or line.startswith("#"):
            trailing_comments.insert(0, line)
        else:
            break
    return "".join(lines[:start] + [replacement] + trailing_comments + lines[end:])

def labels_from_inline(raw):
    # Backlog.md generates JSON-compatible YAML sequences, and single-quoted
    # YAML strings also parse as Python literals.
    try:
        values = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        if not raw.startswith("[") or not raw.endswith("]"):
            raise SystemExit("Agent Backlog: unsupported labels format in " + str(config))
        values = [entry.strip() for entry in raw[1:-1].split(",") if entry.strip()]
        if any(any(ch in entry for ch in ('"', "'", "[", "]")) for entry in values):
            raise SystemExit("Agent Backlog: cannot safely read labels in " + str(config))
    if not isinstance(values, (list, tuple)) or not all(isinstance(v, str) for v in values):
        raise SystemExit("Agent Backlog: labels must be a list of strings in " + str(config))
    return list(values)

def set_labels(content):
    lines = content.splitlines(keepends=True)
    bounds = section(lines, "labels")
    if bounds is None:
        value = json.dumps(confirmation_labels, ensure_ascii=False)
        return content.rstrip("\n") + "\nlabels: " + value + "\n"
    start, end = bounds
    match = re.match(r"^labels:[ \t]*(.*?)[ \t]*$", lines[start].rstrip("\r\n"))
    if match is None:
        raise SystemExit("Agent Backlog: unsupported labels key in " + str(config))
    raw = match.group(1)
    if raw.startswith("["):
        # Retain an inline comment following the closing ']' if present.
        bracket_end = raw.rfind("]")
        if bracket_end == -1:
            raise SystemExit("Agent Backlog: incomplete labels list in " + str(config))
        existing = labels_from_inline(raw[:bracket_end + 1])
        comment = raw[bracket_end + 1:]
        if comment.strip() and not comment.lstrip().startswith("#"):
            raise SystemExit("Agent Backlog: unsupported labels suffix in " + str(config))
        updated = [*existing, *(label for label in confirmation_labels if label not in existing)]
        header = "labels: " + json.dumps(updated, ensure_ascii=False) + comment + "\n"
        return "".join(lines[:start] + [header] + lines[start + 1:])
    if raw and not raw.lstrip().startswith("#"):
        raise SystemExit("Agent Backlog: labels must be a YAML sequence in " + str(config))
    existing = []
    last_item = start
    indentation = "  "
    for i in range(start + 1, end):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([ \t]*)-[ \t]+(.*?)[ \t]*$", line.rstrip("\r\n"))
        if match is None:
            raise SystemExit("Agent Backlog: unsupported block labels in " + str(config))
        last_item = i
        indentation = match.group(1)
        scalar = match.group(2).split(" #", 1)[0].strip()
        if scalar.startswith(("'", '"')):
            try:
                scalar = ast.literal_eval(scalar)
            except (SyntaxError, ValueError):
                raise SystemExit("Agent Backlog: cannot read block label in " + str(config))
        if not isinstance(scalar, str):
            raise SystemExit("Agent Backlog: non-string label in " + str(config))
        existing.append(scalar)
    additions = [indentation + "- " + json.dumps(label, ensure_ascii=False) + "\n"
                 for label in confirmation_labels if label not in existing]
    return "".join(lines[:last_item + 1] + additions + lines[last_item + 1:])

updated = set_labels(set_statuses(text))
if updated == text:
    print("Agent Backlog: workflow configuration already current.")
else:
    # Atomic replacement avoids exposing a half-written file to the browser.
    handle, temporary = tempfile.mkstemp(prefix="." + config.name + ".", dir=config.parent)
    try:
        with os.fdopen(handle, "w") as output:
            output.write(updated)
        os.chmod(temporary, stat.S_IMODE(config.stat().st_mode))
        os.replace(temporary, config)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("Agent Backlog: configured eight stages and two confirmation labels in " + str(config))
PYCONFIG
