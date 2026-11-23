"""Move the retired browser skill outside discovery, preserving its contents."""
import json
import os
from pathlib import Path
import tempfile

home = Path.home()
codex = Path(os.environ.get("CODEX_HOME") or home / ".codex")
locations = {"codex": codex / "skills/agent-browser", "agents": home / ".agents/skills/agent-browser"}
lock = home / ".agents/.skill-lock.json"
metadata = json.loads(lock.read_text()) if lock.is_file() else {}
entry = metadata.get("skills", {}).get("agent-browser")
if any(os.path.lexists(path) for path in locations.values()) or entry is not None:
    root = home / "Library/Application Support/dotfiles/retired-skills"
    root.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="agent-browser-", dir=root))
    if entry is not None:
        (backup / "lock-entry.json").write_text(json.dumps(entry, indent=2) + "\n")
    for name, source in locations.items():
        if os.path.lexists(source):
            source.rename(backup / name)
    if entry is not None:
        del metadata["skills"]["agent-browser"]
        with tempfile.NamedTemporaryFile(mode="w", dir=lock.parent, delete=False) as temp:
            json.dump(metadata, temp, indent=2)
            temp.write("\n")
        os.replace(temp.name, lock)
    print(f"Previous browser skill preserved at {backup}")
