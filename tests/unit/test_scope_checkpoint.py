"""Observable Codex Scope & Effort hook contracts (not semantic LLM judgment)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "home/dot_codex/hooks-json/scope-checkpoint/executable_checkpoint.py"
)
SESSION = "thread-42"
TURN = "turn-1"
CWD = "/workspace/dcp-project"


def run_script(tmp_path: Path, *args: str, event: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=json.dumps(event) if event is not None else None,
        capture_output=True,
        text=True,
        env={**os.environ, "CODEX_HOME": str(tmp_path / ".codex")},
        check=False,
    )


def event(kind: str, *, turn: str = TURN, cwd: str = CWD, tool: str = "apply_patch",
          command: str = "*** Begin Patch") -> dict:
    return {
        "hook_event_name": kind, "session_id": SESSION, "turn_id": turn,
        "cwd": cwd, "tool_name": tool, "tool_input": {"command": command},
    }


def record(tmp_path: Path, *, turn: str = TURN, cwd: str = CWD,
           classification: str = "routine", decision: str = "proceed",
           baseline: str = "DCP-1 AC: upload endpoint", effort: str = "20-40 minutes",
           budget: str = "unknown") -> subprocess.CompletedProcess[str]:
    return run_script(
        tmp_path, "record", "--session-id", SESSION, "--turn-id", turn,
        "--cwd", cwd, "--baseline", baseline, "--change", "Focused upload regression test",
        "--source", "review comment", "--classification", classification,
        "--reason", "Existing AC needs an executable happy-path verification",
        "--human-effort", effort, "--remaining-budget", budget, "--decision", decision,
    )


def result(tmp_path: Path, event_data: dict) -> dict:
    outcome = run_script(tmp_path, "hook", event=event_data)
    assert outcome.returncode == 0, outcome.stderr
    return json.loads(outcome.stdout) if outcome.stdout else {}


def test_native_hook_invocation_enforces_checkpoint_without_local_toggle(tmp_path):
    # Codex controls whether to invoke the hook. No separate enable command is required.
    blocked = result(tmp_path, event("PreToolUse"))
    assert blocked["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not (tmp_path / ".codex/scope-checkpoint/enabled").exists()
    for obsolete_command in ("enable", "disable", "status"):
        assert run_script(tmp_path, obsolete_command).returncode != 0


def test_missing_record_blocks_write_but_not_read_only_research(tmp_path):
    assert result(tmp_path, event("PreToolUse", tool="Bash", command="git status")) == {}
    blocked = result(tmp_path, event("PreToolUse"))
    assert blocked["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "missing" in blocked["hookSpecificOutput"]["permissionDecisionReason"].lower()


def test_in_scope_record_allows_edit_and_is_isolated_to_turn_and_workspace(tmp_path):
    saved = record(tmp_path)
    assert saved.returncode == 0, saved.stderr
    assert result(tmp_path, event("PreToolUse")) == {}
    assert result(tmp_path, event("PreToolUse", tool="Bash", command="touch demo.txt")) == {}
    assert result(tmp_path, event("PreToolUse", turn="turn-2"))["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert result(tmp_path, event("PreToolUse", cwd="/workspace/other"))["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert result(tmp_path, {**event("PreToolUse"), "session_id": "another-session"})["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("classification", ["disputed", "expansion", "unknown"])
def test_unresolved_scope_cannot_be_marked_safe(tmp_path, classification):
    saved = record(tmp_path, classification=classification)
    assert saved.returncode == 1
    assert "cannot be marked proceed" in saved.stderr


def test_missing_baseline_does_not_allow_proceed(tmp_path):
    saved = record(tmp_path, baseline="unknown")
    assert saved.returncode == 1
    assert "missing scope baseline" in saved.stderr


def test_significant_effort_without_budget_does_not_allow_proceed(tmp_path):
    saved = record(tmp_path, effort="significant", budget="unknown")
    assert saved.returncode == 1
    assert "unknown budget" in saved.stderr


def test_pause_record_prevents_mutation(tmp_path):
    assert record(tmp_path, decision="pause", classification="disputed").returncode == 0
    blocked = result(tmp_path, event("PreToolUse", tool="mcp__fs__write_file"))
    assert "PAUSE" in blocked["hookSpecificOutput"]["permissionDecisionReason"]
    assert result(tmp_path, event("PreToolUse", tool="mcp__fs__read_file")) == {}


def test_user_prompt_provides_turn_scoped_instruction_when_invoked(tmp_path):
    reminder = result(tmp_path, event("UserPromptSubmit"))
    context = reminder["hookSpecificOutput"]["additionalContext"]
    assert SESSION in context and TURN in context
    assert str(SCRIPT) in context and "record --session-id" in context
    assert "no-scope-creep conclusion" in context


def test_shell_recorder_is_exempt_but_compound_command_is_not(tmp_path):
    cmd = f"{sys.executable} {SCRIPT} record --session-id {SESSION} --turn-id {TURN}"
    assert result(tmp_path, event("PreToolUse", tool="Bash", command=cmd)) == {}
    mixed = result(tmp_path, event("PreToolUse", tool="Bash", command=cmd + "; touch demo.txt"))
    assert mixed["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    ("tool", "input_key"),
    [
        pytest.param("Bash", "command", id="bash-command"),
        pytest.param("exec_command", "cmd", id="native-exec-cmd"),
        pytest.param("exec_command", "command", id="exec-command-fallback"),
    ],
)
def test_shell_gate_allows_recording_and_read_only_commands_before_checkpoint(
    tmp_path, tool, input_key,
):
    # Arrange: Codex invoked the hook, but no assessment has been recorded.
    recorder = f"{sys.executable} {SCRIPT} record --session-id {SESSION} --turn-id {TURN}"

    # Act: send real hook-shaped shell inputs through the public hook entrypoint.
    def invoke(command):
        request = event("PreToolUse", tool=tool)
        request["tool_input"] = {input_key: command}
        return result(tmp_path, request)

    # Assert: recording remains possible while actual writes are still denied.
    assert invoke(recorder) == {}
    assert invoke("git status") == {}
    assert invoke("touch demo.txt")["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert invoke(recorder + "; touch demo.txt")["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_native_exec_command_with_missing_or_invalid_cmd_is_not_exempt(tmp_path):
    request = event("PreToolUse", tool="exec_command")
    for tool_input in ({}, {"cmd": 123}, {"cmd": None}):
        request["tool_input"] = tool_input
        blocked = result(tmp_path, request)
        assert blocked["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_unrecognized_commands_are_checked_conservatively(tmp_path):
    assert result(tmp_path, event("PreToolUse", tool="Bash", command="python3 -c 'print(1)'"))["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert result(tmp_path, event("PreToolUse", tool="mcp__fs__rename_file"))["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_legacy_activation_file_is_ignored(tmp_path):
    marker = tmp_path / ".codex/scope-checkpoint/enabled"
    marker.parent.mkdir(parents=True)
    marker.touch()
    assert result(tmp_path, event("PreToolUse"))["hookSpecificOutput"]["permissionDecision"] == "deny"
    marker.unlink()
    assert result(tmp_path, event("PreToolUse"))["hookSpecificOutput"]["permissionDecision"] == "deny"
