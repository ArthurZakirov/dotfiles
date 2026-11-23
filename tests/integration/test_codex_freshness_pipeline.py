"""The desktop shortcut and Codex hook observe the same three-stage audit."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "home/dot_codex/hooks-json/agents-md-freshness/pipeline.py"
HOOK = ROOT / "home/dot_codex/hooks-json/agents-md-freshness/executable_check.py"
DESKTOP = ROOT / "home/dot_hammerspoon/bin/executable_agents_md_pipeline"
SESSION = "01a1935b-e50c-7d52-a754-3f81fdffcaee"


@pytest.mark.parametrize("guidance_changed", [False, True])
def test_hook_reports_stale_main_even_when_session_is_current(tmp_path, guidance_changed):
    # GIVEN a private, offline Git remote with a newer commit than local main
    environment = {
        **os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(tmp_path),
    }

    def git(*args, cwd=None):
        return subprocess.run(
            ["git", "-c", "user.name=CI Test", "-c", "user.email=ci@example.invalid",
             "-c", "commit.gpgsign=false", *args],
            cwd=cwd, env=environment, check=True, capture_output=True, text=True,
        )

    repo = tmp_path / "dotfiles"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    source = repo / "home/dot_codex/AGENTS.md.tmpl"
    source.parent.mkdir(parents=True)
    source.write_text("global instructions\n")
    git("add", ".", cwd=repo)
    git("commit", "-qm", "Original guidance", cwd=repo)
    remote = tmp_path / "remote.git"
    git("clone", "-q", "--bare", str(repo), str(remote))
    git("remote", "add", "origin", str(remote), cwd=repo)

    publisher = tmp_path / "publisher"
    git("clone", "-q", str(remote), str(publisher))
    (publisher / ("home/dot_codex/AGENTS.md.tmpl" if guidance_changed else "unrelated")).write_text("updated guidance\n")
    git("add", ".", cwd=publisher)
    git("commit", "-qm", "Update global guidance", cwd=publisher)
    git("push", "-q", "origin", "main", cwd=publisher)


    # The Codex session has already loaded the installed guidance correctly.
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "AGENTS.md").write_text("global instructions\n")
    history = home / "sessions"
    history.mkdir()
    transcript = history / f"rollout-test-{SESSION}.jsonl"
    events = [
        {"type": "session_meta", "payload": {"id": SESSION}},
        {"type": "world_state", "payload": {
            "full": True, "state": {"agents_md": {"text": "global instructions\n"}}
        }},
    ]
    transcript.write_text("".join(json.dumps(item) + "\n" for item in events))
    installed = home / "hooks-json/agents-md-freshness"
    installed.mkdir(parents=True)
    shutil.copyfile(HOOK, installed / "check.py")
    shutil.copyfile(SHARED, installed / "pipeline.py")

    # WHEN the desktop entrypoint and real Codex hook examine the same session
    desktop = subprocess.run(
        [sys.executable, str(DESKTOP), "--repo", str(repo),
         "--codex-home", str(home), "--session-id", SESSION],
        env=environment, text=True, capture_output=True, check=True, timeout=20,
    )
    hook = subprocess.run(
        [sys.executable, str(installed / "check.py"), "--repo", str(repo),
         "--codex-home", str(home), "--no-notify"],
        input=json.dumps({
            "session_id": SESSION, "transcript_path": str(transcript),
            "hook_event_name": "Stop",
        }),
        env=environment, text=True, capture_output=True, check=True, timeout=20,
    )

    # THEN the hook warns for the same outdated stage as the desktop pipeline.
    stages = json.loads(desktop.stdout)["stages"]
    assert [stage["key"] for stage in stages] == [
        "local", "deployed", "session"
    ]
    statuses = {stage["key"]: stage["status"] for stage in stages}
    assert json.loads(desktop.stdout)["repository"]["status"] == "outdated"
    assert statuses["local"] == ("outdated" if guidance_changed else "current")
    assert statuses["session"] == "current"
    message = json.loads(hook.stdout)["systemMessage"]
    assert "Chezmoi repository out of sync" in message
    assert ("Codex AGENTS.md out of sync" in message) == guidance_changed
    for stage in stages if guidance_changed else []:
        symbol = {"current": "✓", "outdated": "✕", "unknown": "?"}[stage["status"]]
        assert f"{symbol} {stage['label']}: {stage['detail']}" in message

    # An identical hook event must not issue the same warning a second time.
    repeated = subprocess.run(
        [sys.executable, str(installed / "check.py"), "--repo", str(repo),
         "--codex-home", str(home), "--no-notify"],
        input=json.dumps({"session_id": SESSION, "transcript_path": str(transcript)}),
        env=environment, text=True, capture_output=True, check=True, timeout=20,
    )
    assert repeated.stdout == ""
