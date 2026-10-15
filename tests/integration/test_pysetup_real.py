"""Exercise real uv, Poetry, pysetup, and the actual interpreter end-to-end.

Run in isolated Linux CI with a dependency-free, freshly generated lockfile.
Unlike editor tests, this executes the real environment provisioning program.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYSETUP = ROOT / "home/dot_local/bin/executable_pysetup"
POETRY = [
    "uv", "tool", "run", "--from", "poetry==2.4.1",
    "--with", "poetry-plugin-export==1.10.1", "poetry",
]

pytestmark = pytest.mark.skipif(
    not (sys.platform.startswith("linux") and os.getenv("CI") == "true"),
    reason="Real dependency installation is only executed in isolated Linux CI",
)


def command(args, directory, home):
    return subprocess.run(
        [str(arg) for arg in args], cwd=directory, capture_output=True,
        text=True, env={**os.environ, "HOME": str(home)}, check=True,
    )


def test_real_pysetup_prepares_interpreter_then_syncs_lock(tmp_path):
    assert shutil.which("uv"), "CI must install the actual uv executable"
    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "project"
    repo.mkdir()
    command(["git", "init", "-q"], repo, home)
    (repo / "pyproject.toml").write_text(
        '[tool.poetry]\n'
        'name = "review-test"\n'
        'version = "0.1.0"\n'
        'package-mode = false\n'
        '[tool.poetry.dependencies]\n'
        'python = "^3.12"\n'
    )
    command([*POETRY, "lock"], repo, home)
    assert (repo / "poetry.lock").is_file()

    # The first phase must create a valid interpreter without package installs.
    first = command([sys.executable, PYSETUP, "--prepare-interpreter", repo], repo, home)
    interpreter = repo / ".venv/bin/python"
    assert "Interpreter ready:" in first.stdout
    assert interpreter.exists()
    assert (repo / ".venv/pyvenv.cfg").is_file()
    selected = command(
        [interpreter, "-c", "import sys; print(sys.prefix)"], repo, home,
    )
    assert Path(selected.stdout.strip()).resolve() == (repo / ".venv").resolve()
    assert not (home / "Library/Caches/pysetup").exists(), (
        "Bootstrap must not export or install any lock dependencies"
    )

    # Execute real Poetry lock checking/export and real uv pip sync/check.
    synced = command([sys.executable, PYSETUP, repo], repo, home)
    assert "Ready:" in synced.stdout
    assert "Locked dependency sync:" in synced.stdout
    assert "Dependency verification:" in synced.stdout
    assert interpreter.exists()

    again = command([sys.executable, PYSETUP, repo], repo, home)
    assert "Environment: reused" in again.stdout
    assert "Lock export: cached" in again.stdout
    assert command(["git", "check-ignore", "-q", ".venv/"], repo, home).returncode == 0
