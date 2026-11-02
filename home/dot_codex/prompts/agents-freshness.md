---
description: Verify whether this Codex chat received the current global AGENTS.md
---

Check the global `AGENTS.md` instructions recorded for **this exact Codex
conversation** against the current global instructions on disk. Do not guess
the active chat from window focus, directory, or rollout modification times.

Use the shell tool in this conversation to execute the following **read-only**
command. Codex supplies `CODEX_THREAD_ID` to its shell tool when available.
If this chat has no shell access, report "Unknown" rather than guessing.

```sh
python3 - <<'PY'
import json
import os
from pathlib import Path
import subprocess
import sys

session = os.environ.get("CODEX_THREAD_ID")
if not session:
    print(json.dumps({"status": "unknown", "reason": "CODEX_THREAD_ID unavailable"}))
else:
    codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    checker = codex_home / "hooks-json/agents-md-freshness/check.py"
    if not checker.is_file():
        print(json.dumps({"status": "unknown", "reason": "Freshness checker not installed"}))
    else:
        subprocess.run(
            [sys.executable, str(checker), "--check", "--session-id", session],
            check=True,
        )
PY
```

Interpret the JSON from the command. Respond with **one concise status**:

- `current`: **✅ AGENTS.md current** — this chat's latest recorded global
  instruction snapshot matches disk. Include the session ID prefix.
- `outdated`: **❌ AGENTS.md outdated** — include the session ID prefix and
  loaded/current source digests when available. A new chat is the reliable
  fallback when the instruction refresh does not occur.
- `unknown`, a failed command, or missing shell access: **❔ AGENTS.md not
  verified** — state the specific reason. Never claim current without evidence.

This checks the last persisted model-visible **global** instruction snapshot;
it cannot verify project-level guidance or the private inference payload.
Do not modify files, restart tools, or silently inspect another chat.
