#!/usr/bin/env python3
"""Advisory Codex hook: compare recorded model-visible AGENTS.md with disk.

Consumes the hook's session-specific transcript path. Never injects instructions,
blocks a turn, or changes Codex transcripts. A missing snapshot is inconclusive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Iterator

PROJECT_SEPARATOR = "\n--- project-doc ---\n"
DIGEST_RE = re.compile(r"(?m)^<!-- Source digest: ([a-f0-9]+) -->$")
SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,128}$")


def rollout_lines(path: Path) -> Iterator[str]:
    """Read plain JSONL or zstd-compressed JSONL without expanding files on disk."""
    if path.name.endswith(".jsonl.zst"):
        executable = shutil.which("zstd")
        if executable is None:
            for candidate in ("/opt/homebrew/bin/zstd", "/usr/local/bin/zstd"):
                if Path(candidate).is_file():
                    executable = candidate
                    break
        if executable is None:
            raise OSError("zstd CLI is not installed")
        process = subprocess.Popen(
            [executable, "-dc", "--", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            assert process.stdout is not None
            yield from process.stdout
        finally:
            assert process.stdout is not None
            process.stdout.close()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if process.returncode != 0:
            raise OSError(f"zstd could not decode {path}")
    else:
        with path.open(encoding="utf-8", errors="replace") as stream:
            yield from stream


def transcript_for(event: dict, codex_home: Path) -> Path | None:
    session = event.get("session_id")
    if not isinstance(session, str) or not SESSION_ID_RE.fullmatch(session):
        return None

    supplied = event.get("transcript_path")
    if isinstance(supplied, str) and supplied:
        path = Path(supplied).expanduser()
        if (
            path.is_file()
            and path.name.endswith((".jsonl", ".jsonl.zst"))
            and session in path.name
        ):
            return path

    matches = []
    for folder in (codex_home / "sessions", codex_home / "archived_sessions"):
        if folder.is_dir():
            matches.extend(folder.rglob(f"rollout-*{session}*.jsonl*"))
    matches = [p for p in matches if p.name.endswith((".jsonl", ".jsonl.zst"))]
    return max(matches, key=lambda p: p.stat().st_mtime, default=None)


def recorded_global_text(path: Path, expected_session: str) -> str | None:
    """Resolve Codex world_state full snapshots and subsequent merge patches."""
    known = False
    snapshot: str | None = None
    session_matched = False

    for line in rollout_lines(path):
        # Most rollout entries are unrelated tool/model events; parsing them
        # incurs substantial overhead for large archived .jsonl.zst files.
        if '"world_state"' not in line and '"session_meta"' not in line:
            continue
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue  # A rollout may end with an incomplete line.
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if record.get("type") == "session_meta":
            session_matched = payload.get("id", payload.get("session_id")) == expected_session
            if not session_matched:
                return None
        if record.get("type") != "world_state":
            continue

        state = payload.get("state")
        if not isinstance(state, dict):
            continue
        if payload.get("full"):
            known = True
            snapshot = None
        if "agents_md" not in state:
            continue
        entry = state["agents_md"]
        if entry is None:
            known = True
            snapshot = None
        elif isinstance(entry, dict):
            if "text" in entry:
                known = True
                snapshot = entry["text"] if isinstance(entry["text"], str) else None
            # A directory-only patch preserves the previous instruction text.

    if not session_matched or not known or not snapshot:
        return None
    return snapshot.split(PROJECT_SEPARATOR, 1)[0].rstrip("\n")


def evaluate(event: dict, codex_home: Path) -> dict:
    session = event.get("session_id")
    if not isinstance(session, str) or not SESSION_ID_RE.fullmatch(session):
        return {"status": "unknown", "reason": "Missing/invalid Codex session ID"}
    transcript = transcript_for(event, codex_home)
    if transcript is None:
        return {"status": "unknown", "reason": "Session transcript not available", "session_id": session}

    # AGENTS.override.md takes precedence over AGENTS.md when present.
    override = codex_home / "AGENTS.override.md"
    current_path = override if override.is_file() else codex_home / "AGENTS.md"
    if not current_path.is_file():
        return {"status": "unknown", "reason": "Global instructions not found", "session_id": session}

    try:
        seen = recorded_global_text(transcript, session)
        if seen is None:
            return {"status": "unknown", "reason": "No model-visible instruction snapshot", "session_id": session}
        current = current_path.read_text(encoding="utf-8").rstrip("\n")
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        return {"status": "unknown", "reason": f"Unable to inspect transcript: {exc}", "session_id": session}

    seen_digest = hashlib.sha256(seen.encode("utf-8")).hexdigest()
    current_digest = hashlib.sha256(current.encode("utf-8")).hexdigest()
    seen_version = DIGEST_RE.search(seen)
    current_version = DIGEST_RE.search(current)
    status = "current" if seen == current else "outdated"
    return {
        "status": status,
        "session_id": session,
        "file": str(current_path),
        "transcript": str(transcript),
        "seen_sha256": seen_digest,
        "current_sha256": current_digest,
        "seen_source_digest": seen_version.group(1) if seen_version else None,
        "current_source_digest": current_version.group(1) if current_version else None,
    }


def warning(result: dict) -> str:
    sid = result["session_id"][:8]
    before = result.get("seen_source_digest") or result["seen_sha256"][:12]
    after = result.get("current_source_digest") or result["current_sha256"][:12]
    return (
        f"⚠️ Codex AGENTS.md out of sync (session {sid}): "
        f"loaded {before}, disk {after}. "
        "This chat last recorded older instructions; start a new chat if it does not refresh."
    )


def notify_macos(message: str) -> None:
    if sys.platform != "darwin":
        return
    # argv avoids shell injection and AppleScript string escaping issues.
    script = (
        "on run argv\n"
        "display notification (item 1 of argv) with title "
        '"Codex AGENTS.md out of sync"\n'
        "end run"
    )
    subprocess.run(
        ["/usr/bin/osascript", "-e", script, message],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=3,
    )


def report_if_changed(result: dict, cache: Path) -> bool:
    """Show each mismatch once per session/version; reset after recovery."""
    import fcntl

    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    sid = result["session_id"]
    target = cache / f"{sid}.json"
    lock = cache / f"{sid}.lock"
    fingerprint = result["seen_sha256"] + ":" + result["current_sha256"]
    with lock.open("a+") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        try:
            previous = json.loads(target.read_text())
        except (OSError, ValueError):
            previous = {}
        if result["status"] == "current":
            if target.exists():
                target.unlink()
            return False
        if previous.get("fingerprint") == fingerprint:
            return False
        target.write_text(json.dumps({"fingerprint": fingerprint}) + "\n")
        target.chmod(0o600)
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Print status instead of acting as a hook")
    parser.add_argument("--session-id", help="Session ID for a manual check")
    parser.add_argument("--transcript-path", help="Rollout file for a manual check")
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser())
    parser.add_argument("--no-notify", action="store_true", help="Suppress macOS notifications (testing)")
    args = parser.parse_args()

    if args.check:
        event = {"session_id": args.session_id, "transcript_path": args.transcript_path}
    else:
        try:
            event = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return 0  # Malformed hook input must never disrupt Codex.
        if not isinstance(event, dict):
            return 0

    result = evaluate(event, args.codex_home)
    if args.check:
        print(json.dumps(result, indent=2))
        return 0

    if result["status"] == "unknown":
        return 0
    if not report_if_changed(result, Path.home() / ".cache/codex-agents-md-freshness"):
        return 0
    message = warning(result)
    print(json.dumps({"systemMessage": message}, ensure_ascii=False))
    if not args.no_notify:
        try:
            notify_macos(message)
        except (OSError, subprocess.SubprocessError):
            pass  # The Codex UI warning remains useful without OS notification.
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(main())
    try:
        raise SystemExit(main())
    except Exception:
        # Hooks are advisory. Unexpected I/O/cache/runtime failures must not
        # interrupt an active Codex session or turn into hook-error noise.
        raise SystemExit(0)
