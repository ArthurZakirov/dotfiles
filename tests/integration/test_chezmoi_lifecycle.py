"""Repository-wide chezmoi lifecycle contract for every currently managed file.

Real chezmoi diff/apply, disposable HOME, no installation hooks or GUI.
The fake editor validates all diff arguments, not a hardcoded file inventory.
"""
from pathlib import Path
import os
import json
import sqlite3
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
    # The isolated HOME represents a fresh machine without a running Codex.
    # The real developer Mac may have ChatGPT Desktop open during the test.
    pgrep = bin_dir / "pgrep"
    pgrep.write_text("#!/bin/sh\nexit 1\n")
    pgrep.chmod(0o755)
    log = tmp_path / "diff-invocations"
    code = bin_dir / "code"
    code.write_text(
        '#!/bin/sh\n'
        'test "$1" = --reuse-window && test "$2" = --diff || exit 22\n'
        'test -f "$3" && test -f "$4" || exit 23\n'
        'printf "%s\\n" "$3 -> $4" >> "$CHEZMOI_DIFF_LOG"\n'
    )
    code.chmod(0o755)
    env = {**os.environ, "HOME": str(home),
           "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "CHEZMOI_DIFF_LOG": str(log),
              "CHEZMOI_CODE_DIFF_SETTLE_SECONDS": "0"}
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

    def recorded_editor_calls() -> int:
        # Adapter invokes code synchronously: no detached-process polling.
        return len(log.read_text().splitlines()) if log.exists() else 0

    assert not list(home.iterdir())
    command("diff", "--exclude", "scripts")
    initial_calls = recorded_editor_calls()
    assert initial_calls > 0

    command("apply", "--exclude", "scripts", "--force")
    for path in managed:
        installed = home / path
        assert installed.exists(), path
        if path.startswith('.local/bin/'):
            assert installed.is_file() and os.access(installed, os.X_OK), (path, 'CLI is not executable')
    # Execute installed entry points in this disposable HOME. A developer's
    # existing ~/.local/bin/session-find or codex_text.py cannot satisfy this.
    codex = home / ".codex"
    codex.mkdir(exist_ok=True)
    with sqlite3.connect(codex / "state_5.sqlite") as db:
        db.execute("CREATE TABLE threads(id TEXT, title TEXT, cwd TEXT, git_branch TEXT, "
                   "git_origin_url TEXT, git_sha TEXT, created_at INTEGER, "
                   "first_user_message TEXT, preview TEXT)")
        db.execute("INSERT INTO threads VALUES(?,?,?,?,?,?,?,?,?)", (
            "11111111-2222-4333-8444-555555555555", "Fresh integration search",
            str(home / "Repos/demo"), "feat/fresh", None, None, 1, "", ""))
    with sqlite3.connect(codex / "thread_history_1.sqlite") as db:
        db.execute("CREATE TABLE thread_items(thread_id TEXT, item_type TEXT, item_json TEXT)")
    for query in [["--branch", "feat/fresh"], ["search", "fresh integration"]]:
        result = subprocess.run([
            str(home / ".local/bin/find-gpt-session"), "--provider", "codex", "--json", *query,
        ], env={**env, "CODEX_HOME": str(codex), "PYTHONPATH": ""},
            capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["total"] == 1, payload
        assert payload["results"][0]["session_id"] == "11111111-2222-4333-8444-555555555555"
    backend = subprocess.run([str(home / ".local/bin/session-find"), "--help"],
                             env=env, capture_output=True, text=True, timeout=10)
    assert backend.returncode == 0 and "--chatgpt-query" in backend.stdout

    command("diff", "--exclude", "scripts")
    assert recorded_editor_calls() == initial_calls
    command("apply", "--exclude", "scripts", "--force")
    command("diff", "--exclude", "scripts")
    assert recorded_editor_calls() == initial_calls

    # Simulate a drifted existing Mac; exercising the same configured diff adapter.
    target = home / ".zshrc"
    original = target.read_text()
    target.write_text(original + "\n# simulated local drift\n")
    command("diff", "--exclude", "scripts")
    assert recorded_editor_calls() > initial_calls
    command("apply", "--exclude", "scripts", "--force")
    assert target.read_text() == original
    after = recorded_editor_calls()
    command("diff", "--exclude", "scripts")
    assert recorded_editor_calls() == after
