#!/usr/bin/env bash
# Keep the one Mac-wide Backlog board consistent across both Mac profiles.
set -euo pipefail

board_root="${AGENT_BACKLOG_DIR:-$HOME/.local/share/agent-backlog}"
cli="$HOME/.local/bin/agent-backlog"
if [[ ! -x "$cli" ]]; then
  echo "Agent Backlog: CLI not yet provisioned; skipping status configuration." >&2
  exit 0
fi
# Initialize once if needed, independent of the current checkout.
"$cli" config get statuses >/dev/null

/usr/bin/python3 - "$board_root/backlog/config.yml" <<'PYCONFIG'
from pathlib import Path
import json
import re
import sys

config = Path(sys.argv[1])
statuses = ('To Do', 'In Progress', 'Pushed', 'PR', 'Merged',
            'STG', 'PRD', 'Done')
confirmation_labels = ('✅ Reviewed', '✅ Behavior tested')
content = config.read_text()

new_statuses = 'statuses: ' + json.dumps(statuses, ensure_ascii=False)
updated, count = re.subn(r'(?m)^statuses:.*$', lambda _: new_statuses, content)
if count != 1:
    raise SystemExit('Expected exactly one statuses key in ' + str(config))

# Preserve user-defined labels; Backlog.md's generated config uses an inline
# JSON-compatible YAML sequence. Refuse unfamiliar forms instead of dropping data.
pattern = r'(?m)^labels: (\[.*\])$'
matches = list(re.finditer(pattern, updated))
if len(matches) != 1:
    raise SystemExit('Expected one inline labels list in ' + str(config))
existing = json.loads(matches[0].group(1))
if not isinstance(existing, list) or not all(isinstance(label, str) for label in existing):
    raise SystemExit('Expected a labels list of strings in ' + str(config))
labels = [*existing, *(name for name in confirmation_labels if name not in existing)]
updated = updated[:matches[0].start()] + 'labels: ' + json.dumps(labels, ensure_ascii=False) + updated[matches[0].end():]

if updated != content:
    config.write_text(updated)
    print('Agent Backlog: configured eight stages and two confirmation labels.')
else:
    print('Agent Backlog: workflow configuration already current.')
PYCONFIG
