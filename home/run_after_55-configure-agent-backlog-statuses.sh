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
import re
import sys

config = Path(sys.argv[1])
statuses = ('To Do', 'In Progress', 'Local Review', 'Pushed',
            'PR', 'Merged', 'STG', 'PRD', 'Done')
new_line = 'statuses: [' + ', '.join(f'"{status}"' for status in statuses) + ']'
content = config.read_text()
updated, count = re.subn(r'(?m)^statuses:.*$', new_line, content)
if count != 1:
    raise SystemExit('Expected exactly one statuses key in ' + str(config))
if updated != content:
    config.write_text(updated)
    print('Agent Backlog: configured nine shared workflow columns.')
else:
    print('Agent Backlog: workflow columns already current.')
PYCONFIG
