#!/bin/bash
# Read the same machine-local directory used by repo-refresh.
python3 - <<'PYCODE'
import json
from pathlib import Path

config = Path.home() / ".config/repo-refresh/config.json"
root = Path(json.loads(config.read_text())["root"]).expanduser() if config.exists() else Path.home() / "Repos"
if not root.is_absolute():
    raise SystemExit("Repository root must be an absolute path")
print(root)
PYCODE
