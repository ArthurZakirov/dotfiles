"""Repository-wide chezmoi lifecycle contract for every currently managed file.

Real chezmoi diff/apply, disposable HOME, no installation hooks or GUI.
The fake editor validates all diff arguments, not a hardcoded file inventory.
"""
from pathlib import Path
import os
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_full_managed_tree_diff_apply_and_upgrade(profile, tmp_path, profile_factory):
    """An empty HOME, repeated apply and a modified managed file all work."""
    rendered = profile_factory.render(profile)
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "diff-invocations"
    code = bin_dir / "code"
    code.write_text(
        '#!/bin/sh\n'
        'test "$1" = --wait && test "$2" = --diff || exit 22\n'
        'test -f "$3" && test -f "$4" || exit 23\n'
        'printf "%s\\n" "$3 -> $4" >> "$CHEZMOI_DIFF_LOG"\n'
    )
    code.chmod(0o755)
    env = {**os.environ, "HOME": str(home),
           "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "CHEZMOI_DIFF_LOG": str(log),
           "DOTFILES_SKIP_OPTIONAL_APPS": "1"}
    config = rendered.config

    def command(action, *args):
        result = subprocess.run([
            "chezmoi", "--source", str(ROOT / "home"),
            "--config", str(config), "--destination", str(home),
            action, *args,
        ], env=env, text=True, capture_output=True, timeout=45)
        assert result.returncode == 0, (action, result.stdout, result.stderr)
        return result.stdout

    # Discover managed paths dynamically, including files added by future features.
    managed = command("managed", "--include", "files").splitlines()
    assert managed
    assert any(".zshrc" in path for path in managed)
    assert any(".local/bin/" in path for path in managed)
    assert not any("__pycache__" in path or path.endswith(".pyc") for path in managed)

    assert not list(home.iterdir())
    command("diff", "--exclude", "scripts")
    assert log.exists() and log.read_text().strip()
    initial_calls = len(log.read_text().splitlines())

    command("apply", "--exclude", "scripts", "--force")
    for path in managed:
        assert (home / path).exists(), path
    command("diff", "--exclude", "scripts")
    assert len(log.read_text().splitlines()) == initial_calls
    command("apply", "--exclude", "scripts", "--force")
    command("diff", "--exclude", "scripts")
    assert len(log.read_text().splitlines()) == initial_calls

    # Simulate a drifted existing Mac; exercising the same configured diff adapter.
    target = home / ".zshrc"
    original = target.read_text()
    target.write_text(original + "\n# simulated local drift\n")
    command("diff", "--exclude", "scripts")
    assert len(log.read_text().splitlines()) > initial_calls
    command("apply", "--exclude", "scripts", "--force")
    assert target.read_text() == original
    after = len(log.read_text().splitlines())
    command("diff", "--exclude", "scripts")
    assert len(log.read_text().splitlines()) == after
