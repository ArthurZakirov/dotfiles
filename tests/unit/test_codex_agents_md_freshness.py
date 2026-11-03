"""Session-specific model-visible guidance freshness, including compressed rollouts."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "home/dot_codex/hooks-json/agents-md-freshness/executable_check.py"
SID = "01a1935b-e50c-7d52-a754-3f81fdffcaee"


def snapshot_entry(instructions: str, *, full: bool = True) -> dict:
    return {"type": "world_state", "payload": {"full": full, "state": {"agents_md": {"directory": "/repo", "text": instructions}}}}


def make_rollout(root: Path, instructions: str | None, *, compressed=False, session_id=SID, changes=None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"rollout-example-{session_id}.jsonl"
    records = [{"type": "session_meta", "payload": {"id": session_id, "cwd": "/repo"}}]
    if instructions is not None:
        records.append(snapshot_entry(instructions))
    records.extend(changes or [])
    raw = "".join(json.dumps(item) + "\n" for item in records)
    if compressed:
        if not shutil.which("zstd"):
            pytest.skip("zstd CLI not installed")
        zst = path.with_suffix(".jsonl.zst")
        subprocess.run(["zstd", "-q", "-o", str(zst)], input=raw, text=True, check=True)
        return zst
    path.write_text(raw)
    return path


def run_check(tmp_path: Path, path: Path | None, *, hook=False):
    args = [sys.executable, str(SCRIPT), "--codex-home", str(tmp_path / ".codex")]
    if not hook:
        args += ["--check", "--session-id", SID]
        if path:
            args += ["--transcript-path", str(path)]
    else:
        args += ["--no-notify"]
    event = {"session_id": SID, "hook_event_name": "Stop", "transcript_path": str(path) if path else None}
    return subprocess.run(
        args, input=json.dumps(event) if hook else None, text=True, capture_output=True,
        env={**os.environ, "HOME": str(tmp_path)}, check=True,
    )


@pytest.mark.parametrize(("compressed", "outdated"), [
    pytest.param(False, False, id="plain-current"),
    pytest.param(False, True, id="plain-outdated"),
    pytest.param(True, False, id="zstd-current"),
    pytest.param(True, True, id="zstd-outdated"),
])
def test_check_compares_global_instructions_from_both_rollout_formats(tmp_path, compressed, outdated):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "AGENTS.md").write_text("# Global\nupdated\n")
    content = "# Global\nold\n" if outdated else "# Global\nupdated\n"
    path = make_rollout(home / "sessions/2026/11/02", content, compressed=compressed)

    result = json.loads(run_check(tmp_path, path).stdout)

    assert result["status"] == ("outdated" if outdated else "current")
    assert result["session_id"] == SID


def test_project_guidance_suffix_does_not_invalidate_current_global(tmp_path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "AGENTS.md").write_text("global\n")
    path = make_rollout(home / "sessions", "global\n\n--- project-doc ---\n\nproject rules\n")

    result = json.loads(run_check(tmp_path, path).stdout)

    assert result["status"] == "current"


def test_latest_world_state_patch_wins_over_old_snapshot(tmp_path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "AGENTS.md").write_text("new\n")
    path = make_rollout(home / "sessions", "old\n", changes=[snapshot_entry("new\n", full=False)])

    result = json.loads(run_check(tmp_path, path).stdout)

    assert result["status"] == "current"


@pytest.mark.parametrize(("tail", "expect"), [
    pytest.param([{"type": "world_state", "payload": {"full": False, "state": {"agents_md": {"directory": "/new"}}}}], "outdated", id="directory-only-preserves-text"),
    pytest.param([{"type": "world_state", "payload": {"full": False, "state": {"agents_md": {"text": None}}}}], "unknown", id="removed-instructions"),
])
def test_partial_patches_are_handled_conservatively(tmp_path, tail, expect):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "AGENTS.md").write_text("new\n")
    path = make_rollout(home / "sessions", "old\n", changes=tail)

    result = json.loads(run_check(tmp_path, path).stdout)

    assert result["status"] == expect


def test_mismatched_session_identity_and_missing_snapshot_never_warn(tmp_path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "AGENTS.md").write_text("new\n")
    path = make_rollout(home / "sessions", None)
    assert json.loads(run_check(tmp_path, path).stdout)["status"] == "unknown"
    other = make_rollout(home / "sessions", "old\n", session_id="different-session-identity")
    event = {"session_id": SID, "transcript_path": str(other)}
    outcome = subprocess.run(
        [sys.executable, str(SCRIPT), "--codex-home", str(home)],
        input=json.dumps(event), text=True, capture_output=True, check=True,
        env={**os.environ, "HOME": str(tmp_path)},
    )
    assert outcome.stdout == ""


def test_global_override_is_authoritative(tmp_path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "AGENTS.md").write_text("original\n")
    (home / "AGENTS.override.md").write_text("override\n")
    path = make_rollout(home / "sessions", "override\n")

    result = json.loads(run_check(tmp_path, path).stdout)

    assert result["status"] == "current"
    assert result["file"].endswith("AGENTS.override.md")


def test_hook_warns_once_per_mismatch_and_clears_on_refresh(tmp_path):
    home = tmp_path / ".codex"
    home.mkdir()
    file = home / "AGENTS.md"
    file.write_text("v2\n")
    path = make_rollout(home / "sessions", "v1\n")

    first = run_check(tmp_path, path, hook=True)
    repeated = run_check(tmp_path, path, hook=True)
    file.write_text("v1\n")
    recovered = run_check(tmp_path, path, hook=True)
    file.write_text("v3\n")
    new_mismatch = run_check(tmp_path, path, hook=True)

    payload = json.loads(first.stdout)
    assert "systemMessage" in payload
    assert "out of sync" in payload["systemMessage"]
    assert repeated.stdout == ""
    assert recovered.stdout == ""
    assert json.loads(new_mismatch.stdout)["systemMessage"] != payload["systemMessage"]


def test_compressed_transcript_is_discovered_by_session_id(tmp_path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "AGENTS.md").write_text("v2\n")
    make_rollout(home / "sessions/2026/11/02", "v1\n", compressed=True)

    result = json.loads(run_check(tmp_path, None).stdout)

    assert result["status"] == "outdated"
    assert result["transcript"].endswith(".jsonl.zst")


def test_missing_transcript_does_not_modify_anything(tmp_path):
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "AGENTS.md").write_text("new\n")

    result = run_check(tmp_path, None, hook=True)

    assert result.stdout == ""
    assert not (tmp_path / ".cache").exists()

def test_empty_valid_instruction_snapshot_is_not_unknown(tmp_path):
    # GIVEN the session loaded valid but empty global instructions
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "AGENTS.md").write_text("# Newly populated\n")
    transcript = make_rollout(home / "sessions", "")

    # WHEN the public checker compares the recorded and current instructions
    result = json.loads(run_check(tmp_path, transcript).stdout)

    # THEN it reports confirmed outdated instructions rather than unknown
    assert result["status"] == "outdated"


def test_partial_install_without_shared_pipeline_never_breaks_codex(tmp_path):
    # GIVEN check.py installed before the new shared pipeline.py
    home = tmp_path / ".codex"
    installed = home / "hooks-json/agents-md-freshness"
    installed.mkdir(parents=True)
    script = installed / "check.py"
    shutil.copyfile(SCRIPT, script)
    (home / "AGENTS.md").write_text("new\n")
    transcript = make_rollout(home / "sessions", "old\n")
    event = {"session_id": SID, "transcript_path": str(transcript)}
    command = [sys.executable, str(script), "--codex-home", str(home)]

    # WHEN an automatic hook is fired during the installation
    hook = subprocess.run(
        command + ["--no-notify"], input=json.dumps(event),
        env={**os.environ, "HOME": str(tmp_path)}, text=True,
        capture_output=True, check=True,
    )

    # THEN the hook remains advisory and does not raise an import error
    assert hook.stdout == ""
    assert hook.stderr == ""
    assert not (tmp_path / ".cache").exists()

    # The session-only diagnostic remains usable during partial installation.
    diagnostic = subprocess.run(
        command + ["--check", "--session-id", SID,
                   "--transcript-path", str(transcript)],
        env={**os.environ, "HOME": str(tmp_path)}, text=True,
        capture_output=True, check=True,
    )
    assert json.loads(diagnostic.stdout)["status"] == "outdated"
