"""Tests for the installed Codex CLI status provider entrypoint."""

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "home/dot_local/bin/executable_codex-agents-status"
THREAD = "01234567-89ab-cdef-0123-456789abcdef"


def run_provider(codex_home: Path, thread_id: str | None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CODEX_HOME": str(codex_home)}
    if thread_id is not None:
        env["CODEX_THREAD_ID"] = thread_id
    else:
        env.pop("CODEX_THREAD_ID", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env, text=True, capture_output=True, timeout=8,
    )


def test_reports_five_actual_pipeline_states_without_reinterpreting_unknown(tmp_path):
    pipeline = tmp_path / "hooks-json/agents-md-freshness/pipeline.py"
    pipeline.parent.mkdir(parents=True)
    payload = {
        "overall": "outdated",
        "stages": [
            {"key": "github", "status": "current"},
            {"key": "local", "status": "unknown"},
            {"key": "generated", "status": "current"},
            {"key": "deployed", "status": "current"},
            {"key": "session", "status": "outdated"},
        ],
    }
    pipeline.write_text(
        "import json, sys\n"
        f"assert sys.argv[-1] == {THREAD!r}\n"
        f"print(json.dumps({payload!r}))\n"
    )

    result = run_provider(tmp_path, THREAD)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "AGENTS G✓ L? R✓ C✓ S✕\n"


def test_missing_session_or_pipeline_does_not_show_false_green(tmp_path):
    for session_id in (None, THREAD):
        result = run_provider(tmp_path, session_id)

        assert result.returncode == 0, result.stderr
        assert result.stdout == "AGENTS G? L? R? C? S?\n"


def test_invalid_pipeline_response_returns_unknown(tmp_path):
    pipeline = tmp_path / "hooks-json/agents-md-freshness/pipeline.py"
    pipeline.parent.mkdir(parents=True)
    pipeline.write_text("print('not JSON')\n")

    result = run_provider(tmp_path, THREAD)

    assert result.returncode == 0
    assert result.stdout == "AGENTS G? L? R? C? S?\n"
