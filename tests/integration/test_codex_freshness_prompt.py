"""The on-demand Codex command must verify the invoking chat, not another chat."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "home/dot_codex/prompts/agents-freshness.md"


@pytest.mark.parametrize("profile", ("personal", "professional"))
def test_custom_prompt_is_chezmoi_managed(profile_factory, profile):
    rendered = profile_factory.render(profile)
    managed = profile_factory.chezmoi(
        rendered.config, "managed", "--include", "files"
    ).splitlines()

    assert ".codex/prompts/agents-freshness.md" in managed
    text = profile_factory.chezmoi(
        rendered.config, "cat", str(Path.home() / ".codex/prompts/agents-freshness.md")
    )
    assert "CODEX_THREAD_ID" in text
    assert "hooks-json/agents-md-freshness/check.py" in text


@pytest.fixture
def runnable_prompt(tmp_path):
    source = SOURCE.read_text()
    match = re.search(r"```sh\n(.+?)\n```", source, re.DOTALL)
    assert match is not None
    script = match.group(1)

    home = tmp_path / "codex-home"
    checker = home / "hooks-json/agents-md-freshness/check.py"
    checker.parent.mkdir(parents=True)
    checker.write_text(
        "import json, sys\n"
        "print(json.dumps({'status': 'current', 'session_id': sys.argv[-1],"
        " 'arguments': sys.argv[1:]}))\n"
    )
    return script, home


def test_command_uses_real_session_id_from_shell_environment(runnable_prompt):
    script, home = runnable_prompt
    session = "01a1935b-e50c-7d52-a754-3f81fdffcaee"

    result = subprocess.run(
        ["/bin/sh", "-c", script],
        env={**os.environ, "CODEX_THREAD_ID": session, "CODEX_HOME": str(home)},
        text=True,
        capture_output=True,
        check=True,
    )

    output = json.loads(result.stdout)
    assert output["status"] == "current"
    assert output["session_id"] == session
    assert output["arguments"] == ["--check", "--session-id", session]


def test_command_never_guesses_a_session_when_context_is_missing(runnable_prompt):
    script, home = runnable_prompt
    env = {**os.environ, "CODEX_HOME": str(home)}
    env.pop("CODEX_THREAD_ID", None)

    result = subprocess.run(
        ["/bin/sh", "-c", script],
        env=env, text=True, capture_output=True, check=True,
    )

    assert json.loads(result.stdout) == {
        "status": "unknown",
        "reason": "CODEX_THREAD_ID unavailable",
    }


def test_command_reports_missing_checker_as_unknown(runnable_prompt):
    script, home = runnable_prompt
    (home / "hooks-json/agents-md-freshness/check.py").unlink()

    result = subprocess.run(
        ["/bin/sh", "-c", script],
        env={**os.environ, "CODEX_HOME": str(home), "CODEX_THREAD_ID": "abc"},
        text=True, capture_output=True, check=True,
    )

    assert json.loads(result.stdout)["status"] == "unknown"
    assert "not installed" in json.loads(result.stdout)["reason"]
