"""Warp tab configs resume the requested Codex thread in its original directory."""
from __future__ import annotations

from importlib.machinery import SourceFileLoader
import importlib.util
from pathlib import Path
import shlex
import sqlite3
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "home/dot_hammerspoon/bin/executable_codex_resume_warp"
THREAD_ID = "11111111-2222-4333-8444-555555555555"


@pytest.fixture
def launcher():
    loader = SourceFileLoader("codex_resume_warp", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def codex_home(tmp_path):
    codex = tmp_path / ".codex"
    codex.mkdir()
    with sqlite3.connect(codex / "state_5.sqlite") as con:
        con.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, cwd TEXT)")
        con.execute("INSERT INTO threads VALUES (?, ?)", (THREAD_ID, str(tmp_path)))
    return tmp_path


def test_launch_resumes_exact_session_in_original_workspace(launcher, codex_home):
    requests = []

    def runner(argv, **kwargs):
        requests.append((argv, kwargs))
        name = argv[1].rsplit("/", 1)[-1]
        (codex_home / ".warp/tab_configs" / (name + ".ready")).touch()
        return subprocess.CompletedProcess(argv, 0)

    path = launcher.launch(THREAD_ID, home=codex_home, runner=runner)
    doc = tomllib.loads(path.read_text())
    assert doc["name"] == "Codex 11111111"
    assert doc["panes"][0]["directory"] == str(codex_home.resolve())
    assert shlex.split(doc["panes"][0]["commands"][0]) == [
        str(codex_home / ".hammerspoon/bin/codex_resume_warp"),
        "--resume-when-unlocked", THREAD_ID,
        "--ready-file", str(path.with_suffix(".ready")),
    ]
    assert not path.with_suffix(".ready").exists()
    assert requests[0][0] == ["/usr/bin/open", f"warp://tab_config/{path.stem}"]
    assert path.stat().st_mode & 0o077 == 0
    assert len(list(path.parent.glob("codex_desktop_resume_*.toml"))) == 1


@pytest.mark.parametrize("thread_id", ["; rm -rf ~", "11111111222243338444555555555555", "x", ""])
def test_invalid_thread_never_creates_tab(launcher, tmp_path, thread_id):
    with pytest.raises(launcher.LaunchError):
        launcher.launch(thread_id, home=tmp_path, runner=lambda *_a, **_kw: None)
    assert not (tmp_path / ".warp").exists()


def test_missing_thread_never_creates_tab(launcher, codex_home):
    with pytest.raises(launcher.LaunchError, match="not found"):
        launcher.launch("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", home=codex_home)
    assert not (codex_home / ".warp").exists()


def test_missing_workspace_never_launches_in_home(launcher, codex_home):
    with sqlite3.connect(codex_home / ".codex/state_5.sqlite") as con:
        con.execute("UPDATE threads SET cwd=?", (str(codex_home / "removed"),))
    with pytest.raises(launcher.LaunchError, match="no longer exists"):
        launcher.launch(THREAD_ID, home=codex_home)


def test_warp_rejection_is_failure(launcher, codex_home):
    def reject(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1)
    with pytest.raises(launcher.LaunchError, match="rejected"):
        launcher.launch(THREAD_ID, home=codex_home, runner=reject)


def test_successful_open_without_tab_acknowledgment_is_not_success(launcher, codex_home):
    def dispatch_only(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0)

    with pytest.raises(launcher.LaunchError, match="did not start"):
        launcher.launch(
            THREAD_ID, home=codex_home, runner=dispatch_only, ready_timeout=0.02,
        )


def test_warp_tab_acknowledges_ready_then_resumes_exact_thread(launcher, codex_home):
    ready = codex_home / ".warp/tab_configs/codex_desktop_resume_abc.ready"
    ready.parent.mkdir(parents=True)
    executed = []

    launcher.resume_when_unlocked(
        THREAD_ID, ready, home=codex_home,
        executor=lambda program, argv: executed.append((program, argv)),
    )

    assert ready.is_file()
    assert ready.stat().st_mode & 0o077 == 0
    assert executed == [("codex", ["codex", "resume", THREAD_ID])]


def test_warp_tab_rejects_ready_file_outside_owned_directory(launcher, codex_home):
    ready = codex_home / "elsewhere.ready"
    with pytest.raises(launcher.LaunchError, match="readiness path"):
        launcher.resume_when_unlocked(
            THREAD_ID, ready, home=codex_home, executor=lambda *_: None,
        )
    assert not ready.exists()


def test_warp_tab_waits_for_real_session_file_lock(launcher, codex_home):
    lock_dir = codex_home / ".codex/thread-writer-locks"
    lock_dir.mkdir(parents=True)
    lock = lock_dir / (THREAD_ID + ".lock")
    lock.touch()
    code = (
        "import fcntl,sys; "
        "f=open(sys.argv[1], 'r+b'); "
        "fcntl.flock(f, fcntl.LOCK_EX); "
        "print('LOCKED',flush=True); "
        "sys.stdin.read()"
    )
    holder = subprocess.Popen(
        ["python3", "-c", code, str(lock)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "LOCKED"
        with pytest.raises(launcher.LaunchError, match="did not release"):
            launcher.wait_for_unlocked(THREAD_ID, codex_home, timeout=0.02)
    finally:
        holder.stdin.close()
        holder.wait(timeout=5)

    launcher.wait_for_unlocked(THREAD_ID, codex_home, timeout=0.2)
