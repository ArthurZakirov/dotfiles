"""Contract tests for the Mac-wide Backlog.md wrapper and launchd integration."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "home/dot_local/bin/executable_agent-backlog"
LAUNCH_AGENT = ROOT / "home/private_Library/private_LaunchAgents/com.arthur.agent-backlog.plist.tmpl"


def test_agent_backlog_uses_one_non_git_store_from_different_cwds(tmp_path: Path) -> None:
    # Arrange: a real shell entrypoint with a fake Backlog.md dependency.
    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    fake_backlog = executable_dir / "backlog"
    fake_backlog.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"$1\" == init ]]; then\n"
        "  mkdir -p backlog\n"
        "  echo 'filesystem_only: true' > backlog/config.yml\n"
        "  echo init >> \"$TEST_CALLS\"\n"
        "else\n"
        "  printf '%s\\n' \"$PWD\"\n"
        "fi\n"
    )
    fake_backlog.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    store = home / ".local/share/agent-backlog"
    calls = tmp_path / "calls"
    env = {
        **os.environ,
        "HOME": str(home),
        "AGENT_BACKLOG_DIR": str(store),
        "TEST_CALLS": str(calls),
        "PATH": f"{executable_dir}:{os.environ['PATH']}",
    }
    cwd_a = tmp_path / "a"
    cwd_b = tmp_path / "b"
    cwd_a.mkdir()
    cwd_b.mkdir()

    # Act: use exactly the same wrapper from two unrelated working directories.
    first = subprocess.run(["bash", str(WRAPPER), "task", "list"], cwd=cwd_a, env=env, text=True, capture_output=True, check=True)
    second = subprocess.run(["bash", str(WRAPPER), "task", "list"], cwd=cwd_b, env=env, text=True, capture_output=True, check=True)

    # Assert: a single filesystem-only backlog, initialized once.
    assert first.stdout.strip() == second.stdout.strip() == str(store)
    assert calls.read_text().splitlines() == ["init"]
    assert (store / "backlog/config.yml").is_file()
    assert not (store / ".git").exists()
    assert not (cwd_a / "backlog").exists()
    assert not (cwd_b / "backlog").exists()


def test_launch_agent_uses_clean_environment_and_stable_port() -> None:
    # The provider template syntax is inside element text and remains valid XML.
    root = ET.parse(LAUNCH_AGENT).getroot()
    # Inspect the plist dictionary directly; xml.etree supports only a subset of XPath.
    entries = root.find("dict")
    assert entries is not None
    children = list(entries)
    index = next(i for i, elem in enumerate(children) if elem.tag == "key" and elem.text == "ProgramArguments")
    args = [elem.text for elem in list(children[index + 1])]
    assert args[0:2] == ["/usr/bin/env", "-i"]
    assert "browser" in args and "6420" in args and "--no-open" in args
    assert all("LANGSMITH" not in (value or "") for value in args)
