"""Warp tab configs resume the requested Codex thread in its original directory."""
from __future__ import annotations

from importlib.machinery import SourceFileLoader
import importlib.util
from pathlib import Path
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
        return subprocess.CompletedProcess(argv, 0)

    path = launcher.launch(THREAD_ID, home=codex_home, runner=runner)
    doc = tomllib.loads(path.read_text())
    assert doc["name"] == "Codex 11111111"
    assert doc["panes"][0]["directory"] == str(codex_home.resolve())
    assert doc["panes"][0]["commands"] == [f"codex resume {THREAD_ID}"]
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
