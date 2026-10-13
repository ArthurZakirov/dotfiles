"""Prevent transient Python bytecode from becoming chezmoi-managed dotfiles."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def test_python_bytecode_is_ignored_in_disposable_chezmoi_source(tmp_path):
    """Exercise chezmoi's actual managed and ignored commands with a cold source."""
    source = tmp_path / "source"
    source.mkdir()
    (source / ".chezmoiignore").write_bytes((ROOT / "home/.chezmoiignore").read_bytes())
    managed_dir = source / "dot_local/bin"
    managed_dir.mkdir(parents=True)
    (managed_dir / "executable_pysetup").write_text("#!/bin/sh\nexit 0\n")
    cache = managed_dir / "__pycache__"
    cache.mkdir()
    (cache / "executable_pysetupcpython-315.pyc").write_bytes(b"\0\0binary bytecode")
    (managed_dir / "stray.pyc").write_bytes(b"\0binary bytecode")

    def chezmoi(command):
        return subprocess.run(
            ["chezmoi", "--source", str(source), "--destination", str(tmp_path / "home"), command],
            text=True, capture_output=True, check=True,
        ).stdout.splitlines()

    managed = chezmoi("managed")
    ignored = chezmoi("ignored")
    assert ".local/bin/pysetup" in managed
    assert not any("__pycache__" in entry or entry.endswith(".pyc") for entry in managed)
    assert any("__pycache__" in entry for entry in ignored)
    assert ".local/bin/stray.pyc" in ignored
