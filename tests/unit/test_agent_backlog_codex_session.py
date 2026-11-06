"""Black-box tests for automatic Codex session linking in agent-backlog."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "home/dot_local/bin/executable_agent-backlog"
LINKER = ROOT / "home/dot_local/bin/executable_agent-backlog-codex-session"
SESSION_A = "123e4567-e89b-42d3-a456-426614174000"
SESSION_B = "123e4567-e89b-42d3-a456-426614174001"


FAKE_BACKLOG = r"""#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

db = Path(os.environ["TEST_TASK_DB"])
tasks = json.loads(db.read_text()) if db.exists() else {}
args = sys.argv[1:]
if args[:2] == ["task", "create"]:
    task_id = "AGENT-" + str(len(tasks) + 1)
    tasks[task_id] = {"id": task_id, "comments": []}
    db.write_text(json.dumps(tasks))
    if "--plain" in args:
        print("Task " + task_id + " - Sample task")
    else:
        print("Created task " + task_id)
elif args[:2] == ["task", "edit"]:
    if "AGENT-404" in args:
        print("Task not found", file=sys.stderr)
        sys.exit(7)
    ids = [arg for arg in args[2:] if arg in tasks]
    if "--comment" in args:
        comment = args[args.index("--comment") + 1]
        for task_id in ids:
            tasks[task_id]["comments"].append({"body": comment, "author": "@codex"})
    db.write_text(json.dumps(tasks))
    for task_id in ids:
        print("Updated task " + task_id)
elif args[:2] == ["task", "view"]:
    print(json.dumps({"task": tasks[args[2]]}))
elif args[:2] == ["task", "list"]:
    print(json.dumps({"tasks": list(tasks.values())}))
else:
    print("Unexpected command", file=sys.stderr)
    sys.exit(3)
"""


@pytest.fixture
def environment(tmp_path: Path) -> tuple[dict[str, str], Path]:
    # Arrange: isolated home and fake Backlog CLI, with the actual managed
    # wrapper and link helper as the production entry points.
    home = tmp_path / "home"
    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    backlog = executable_dir / "backlog"
    backlog.write_text(FAKE_BACKLOG)
    backlog.chmod(0o755)
    linker_dir = home / ".local/bin"
    linker_dir.mkdir(parents=True)
    shutil.copyfile(LINKER, linker_dir / "agent-backlog-codex-session")

    board = home / ".local/share/agent-backlog/backlog"
    board.mkdir(parents=True)
    (board / "config.yml").write_text("project_name: Test\n")
    db = tmp_path / "tasks.json"
    env = dict(os.environ)
    env.update({
        "HOME": str(home),
        "AGENT_BACKLOG_DIR": str(home / ".local/share/agent-backlog"),
        "TEST_TASK_DB": str(db),
        "PATH": str(executable_dir) + os.pathsep + env.get("PATH", ""),
    })
    env.pop("CODEX_THREAD_ID", None)
    return env, db


def invoke(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(WRAPPER), *args],
        env=env, capture_output=True, text=True, check=False,
    )


def comments(db: Path, task_id: str) -> list[str]:
    state = json.loads(db.read_text())
    return [comment["body"] for comment in state[task_id]["comments"]]


@pytest.mark.parametrize("plain", [False, True])
def test_create_adds_a_copyable_codex_resume_command(
    environment: tuple[dict[str, str], Path], plain: bool,
) -> None:
    env, db = environment
    env["CODEX_THREAD_ID"] = SESSION_A

    result = invoke(env, "task", "create", "Sample task", *(["--plain"] if plain else []))

    assert result.returncode == 0
    assert "AGENT-1" in result.stdout
    assert comments(db, "AGENT-1") == [
        "Codex session: " + chr(96) + SESSION_A + chr(96) +
        "\n\nResume this conversation in Codex CLI:\n\n" +
        chr(96) * 3 + "bash\ncodex resume " + SESSION_A + "\n" + chr(96) * 3
    ]


def test_edits_deduplicate_current_session_and_record_other_sessions(
    environment: tuple[dict[str, str], Path],
) -> None:
    env, db = environment
    env["CODEX_THREAD_ID"] = SESSION_A
    assert invoke(env, "task", "create", "First").returncode == 0
    assert invoke(env, "task", "create", "Second").returncode == 0

    # Act: repeated changes, a second Codex session and a multi-task edit.
    assert invoke(env, "task", "edit", "AGENT-1", "--status", "In Progress").returncode == 0
    env["CODEX_THREAD_ID"] = SESSION_B
    assert invoke(env, "task", "edit", "AGENT-1", "AGENT-2", "--status", "Pushed").returncode == 0
    assert invoke(env, "task", "edit", "AGENT-1", "--status", "Pushed").returncode == 0

    assert len(comments(db, "AGENT-1")) == 2
    assert len(comments(db, "AGENT-2")) == 2
    assert sum("codex resume " + SESSION_B in c for c in comments(db, "AGENT-1")) == 1


@pytest.mark.parametrize("thread_id", [None, "", "not-a-uuid", "AGENT-1"])
def test_missing_or_invalid_session_never_creates_a_link(
    environment: tuple[dict[str, str], Path], thread_id: str | None,
) -> None:
    env, db = environment
    if thread_id is not None:
        env["CODEX_THREAD_ID"] = thread_id

    created = invoke(env, "task", "create", "Sample task")
    changed = invoke(env, "task", "edit", "AGENT-1", "--status", "Pushed")

    assert created.returncode == changed.returncode == 0
    assert comments(db, "AGENT-1") == []


def test_failed_write_does_not_forge_a_session_link(
    environment: tuple[dict[str, str], Path],
) -> None:
    env, db = environment
    env["CODEX_THREAD_ID"] = SESSION_A
    assert invoke(env, "task", "create", "Sample task").returncode == 0
    before = comments(db, "AGENT-1")

    failed = invoke(env, "task", "edit", "AGENT-404", "--status", "Pushed")

    assert failed.returncode == 7
    assert "Task not found" in failed.stderr
    assert comments(db, "AGENT-1") == before


def test_readonly_operations_do_not_create_session_links(
    environment: tuple[dict[str, str], Path],
) -> None:
    env, db = environment
    assert invoke(env, "task", "create", "Sample task").returncode == 0
    env["CODEX_THREAD_ID"] = SESSION_A

    result = invoke(env, "task", "list", "--json")

    assert result.returncode == 0
    assert comments(db, "AGENT-1") == []
