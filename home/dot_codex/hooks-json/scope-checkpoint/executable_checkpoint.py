#!/usr/bin/env python3
"""Opt-in, turn-scoped Scope & Effort checkpoint for supported Codex tool hooks.

This gate checks that an assessment was recorded, not whether its judgment is
correct or whether Codex actually displayed the assessment in chat.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile


IDENTIFIER = re.compile(r"^[a-zA-Z0-9._:-]{1,150}$")
READ_ONLY_SHELL = {
    "pwd", "ls", "rg", "grep", "head", "tail", "wc", "stat", "which",
    "whoami", "date", "cat", "true", "false", "type",
}
READ_ONLY_GIT = {"status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "merge-base"}
READ_ONLY_TOOLS = ("read", "get", "list", "find", "search", "inspect", "fetch", "lookup", "view")
CLASSIFICATIONS = ("explicit", "routine", "necessary", "disputed", "expansion", "unknown")


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()


def state_root() -> Path:
    return codex_home() / "scope-checkpoint"


def enabled() -> bool:
    return (state_root() / "enabled").is_file()


def checkpoint_path(session: str, turn: str, cwd: str) -> Path:
    if not IDENTIFIER.fullmatch(session) or not IDENTIFIER.fullmatch(turn):
        raise ValueError("invalid session_id or turn_id")
    if not cwd or not Path(cwd).is_absolute():
        raise ValueError("cwd must be absolute")
    key = json.dumps([session, turn, str(Path(cwd).resolve())], separators=(",", ":"))
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return state_root() / "records" / f"{digest}.json"


def save_checkpoint(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def assessment(args: argparse.Namespace) -> int:
    fields = ("baseline", "change", "source", "classification", "reason", "human_effort", "remaining_budget")
    for field in fields:
        value = getattr(args, field)
        if not value or not value.strip() or len(value) > 1800:
            raise ValueError(f"{field} must be nonempty and at most 1800 characters")
    if len(args.reason.strip()) < 12:
        raise ValueError("reason must state the evidence for the classification")
    if args.classification in ("disputed", "expansion", "unknown") and args.decision == "proceed":
        raise ValueError("disputed, expanded, or unknown scope cannot be marked proceed")
    if args.baseline.strip().lower() in ("unknown", "missing", "none") and args.decision == "proceed":
        raise ValueError("missing scope baseline requires pause; do not invent acceptance criteria")
    if args.remaining_budget.strip().lower() in ("unknown", "missing") and args.human_effort.strip().lower() in ("significant", "substantial", "high"):
        if args.decision == "proceed":
            raise ValueError("substantial human effort with unknown budget requires pause")
    path = checkpoint_path(args.session_id, args.turn_id, args.cwd)
    save_checkpoint(path, {field: getattr(args, field).strip() for field in fields} | {
        "decision": args.decision,
        "session_id": args.session_id,
        "turn_id": args.turn_id,
        "cwd": str(Path(args.cwd).resolve()),
    })
    print(json.dumps({"status": "recorded", "decision": args.decision, "classification": args.classification}))
    return 0


def allowed_record_command(command: str) -> bool:
    """Allow a standalone checkpoint CLI invocation, never unrelated shell work.

    Quoted assessment punctuation is data, not a command separator.
    A leading cd into an absolute workspace is permitted because agents often
    prefix terminal calls with the working directory.
    """
    if any(token in command for token in ("\n", "\r", "`", "$(")):
        return False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()")
        lexer.whitespace_split = True
        parts = list(lexer)
    except ValueError:
        return False

    if len(parts) >= 4 and parts[0] == "cd" and parts[2] == "&&":
        if not Path(parts[1]).is_absolute():
            return False
        parts = parts[3:]

    if len(parts) < 3 or Path(parts[0]).name not in (
        "python", "python3", "python3.11", "python3.12", "python3.13",
        "python3.14", "py",
    ):
        return False
    if Path(parts[1]).expanduser().resolve() != Path(__file__).resolve():
        return False
    if parts[2] not in ("record", "status", "disable"):
        return False
    # shlex emits unquoted shell punctuation as punctuation-only tokens,
    # including compound redirections (&>, >|, <>, etc.). Quoted assessment
    # prose may contain punctuation alongside ordinary text without becoming
    # a shell operator.
    shell_punctuation = ";&|<>()"
    return not any(
        part and all(char in shell_punctuation for char in part)
        for part in parts[3:]
    )


def is_read_only_bash(command: str) -> bool:
    # Conservatively block unknown/compound commands, including scripts that can write.
    if not command or re.search(r"[;&|><\n\x60]|\$\(", command):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False
    executable = Path(parts[0]).name
    if executable == "git":
        argv = parts[1:]
        if len(argv) >= 2 and argv[0] == "-C":
            argv = argv[2:]
        return bool(argv) and argv[0] in READ_ONLY_GIT and not any(
            item == "--output" or item.startswith("--output=") or item == "-o"
            for item in argv[1:]
        )
    if executable == "find":
        return not any(arg in ("-exec", "-execdir", "-delete", "-ok", "-okdir") for arg in parts)
    if executable == "sed":
        return len(parts) > 1 and parts[1] == "-n"
    return executable in READ_ONLY_SHELL


def may_write(tool_name: str, tool_input: object) -> bool:
    if tool_name in ("apply_patch", "Edit", "Write"):
        return True
    if tool_name in ("Bash", "exec_command"):
        if not isinstance(tool_input, dict):
            return True
        command = tool_input.get("cmd") if tool_name == "exec_command" else tool_input.get("command")
        if command is None:
            command = tool_input.get("command") if tool_name == "exec_command" else tool_input.get("cmd")
        if not isinstance(command, str):
            return True
        return not (allowed_record_command(command) or is_read_only_bash(command))
    if tool_name in ("update_plan", "spawn_agent"):
        return False
    if tool_name.startswith("mcp__"):
        action = tool_name.rsplit("__", 1)[-1].lower()
        return not any(action.startswith(prefix) for prefix in READ_ONLY_TOOLS)
    # Unknown local function tools may mutate state; do not silently exempt them.
    return True


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def hook(event: dict) -> int:
    if not enabled():
        return 0
    kind = event.get("hook_event_name")
    if kind == "UserPromptSubmit":
        session, turn, cwd = (event.get(key) for key in ("session_id", "turn_id", "cwd"))
        if not all(isinstance(x, str) and x for x in (session, turn, cwd)):
            return 0
        guidance = (
            "Scope checkpoint is enabled. Before a tool that may change files or shared systems, "
            "evaluate the controlling ticket/acceptance criteria, intended change, source, "
            "classification, evidence, remaining human effort and budget. "
            "Tell the user the compact result BEFORE editing, including a justified "
            "no-scope-creep conclusion. Then execute: "
            f"python3 {shlex.quote(str(Path(__file__).resolve()))} record "
            f"--session-id {shlex.quote(session)} --turn-id {shlex.quote(turn)} "
            f"--cwd {shlex.quote(cwd)} "
            "--baseline BASELINE --change CHANGE --source SOURCE "
            "--classification CLASSIFICATION --reason EVIDENCE "
            "--human-effort EFFORT --remaining-budget BUDGET --decision DECISION. "
            "Replace placeholders, quote multiword values. Choose decision=pause "
            "for disputed/expanded scope or missing acceptance criteria; never invent facts. "
            "Record once per coherent change set/turn; renew after the next user request. "
            "Read-only investigation needs no record."
        )
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit", "additionalContext": guidance,
        }}))
        return 0
    if kind != "PreToolUse":
        return 0
    name = event.get("tool_name", "")
    if not may_write(name, event.get("tool_input")):
        return 0
    session, turn, cwd = (event.get(key) for key in ("session_id", "turn_id", "cwd"))
    try:
        path = checkpoint_path(session, turn, cwd)
        record = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, TypeError, OSError, json.JSONDecodeError):
        script = Path(__file__).resolve()
        deny(
            f"Scope & Effort checkpoint missing for this turn. Before editing, tell the user "
            f"your ticket-based assessment, then run python3 {script} record "
            f"--session-id {session} --turn-id {turn} --cwd {shlex.quote(str(cwd))} "
            "--baseline ... --change ... --source ... --classification ... --reason ... "
            "--human-effort ... --remaining-budget ... --decision proceed|pause. "
            "If the ticket scope is unknown, pause and clarify instead."
        )
        return 0
    if record.get("decision") != "proceed":
        deny("Scope & Effort checkpoint recorded PAUSE. Clarify the affected scope before changes.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("enable", "disable", "status", "hook"):
        commands.add_parser(name)
    record = commands.add_parser("record")
    for flag in ("session-id", "turn-id", "cwd", "baseline", "change", "source",
                 "classification", "reason", "human-effort", "remaining-budget"):
        record.add_argument("--" + flag, required=True, choices=CLASSIFICATIONS if flag == "classification" else None)
    record.add_argument("--decision", choices=("proceed", "pause"), required=True)
    args = parser.parse_args()
    if args.command == "enable":
        root = state_root()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
        (root / "enabled").touch(mode=0o600)
        os.chmod(root / "enabled", 0o600)
        print("Scope checkpoint enabled for this Codex home.")
    elif args.command == "disable":
        (state_root() / "enabled").unlink(missing_ok=True)
        print("Scope checkpoint disabled; previous local records remain.")
    elif args.command == "status":
        print(json.dumps({"enabled": enabled()}))
    elif args.command == "record":
        return assessment(args)
    else:
        return hook(json.load(sys.stdin))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"scope-checkpoint: {exc}", file=sys.stderr)
        sys.exit(1)
