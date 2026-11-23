#!/usr/bin/env python3
"""Shared read-only three-stage AGENTS.md audit for desktop and Codex hooks.

Exit zero even when a stage is outdated or unverifiable. Leave the managed checkout and installed files untouched. Missing evidence produces unknown, never false green.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(arguments: list[str], *, timeout: float = 3, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        env={
            **os.environ,
            # GUI applications do not inherit the interactive shell's Homebrew PATH.
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", ""),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o ConnectTimeout=2",
        },
        check=False,
    )


def row(key: str, label: str, status: str, detail: str) -> dict[str, str]:
    return {"key": key, "label": label, "status": status, "detail": detail}


def session_stage(
    session_id: str | None, codex_home: Path, checker: Path,
    session_result: dict | None = None,
) -> dict[str, str]:
    if not session_id:
        return row("session", "Session loaded", "unknown", "Keine Codex-Session erkannt")
    elif session_result is None and not checker.is_file():
        return row("session", "Session loaded", "unknown", "Session-Checker fehlt")
    else:
        try:
            if session_result is None:
                result = run(
                    [sys.executable, str(checker), "--check", "--session-id", session_id,
                     "--codex-home", str(codex_home)],
                    timeout=5,
                )
                payload = json.loads(result.stdout) if result.returncode == 0 else {}
            else:
                payload = session_result
            valid = payload.get("session_id") == session_id
            status = payload.get("status") if valid else "unknown"
            if status == "current":
                detail = f"Session {session_id[:8]} · aktuell"
            elif status == "outdated":
                before = payload.get("seen_source_digest") or (payload.get("seen_sha256") or "")[:12]
                after = payload.get("current_source_digest") or (payload.get("current_sha256") or "")[:12]
                detail = (f"Session {session_id[:8]} · {before} → {after}"
                          if before and after else f"Session {session_id[:8]} · ältere Version")
            else:
                detail = payload.get("reason", "Session nicht verifizierbar")
                status = "unknown"
            return row("session", "Session loaded", status, detail)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return row("session", "Session loaded", "unknown", "Session-Prüfung fehlgeschlagen")

def check(
    repo: Path | None, codex_home: Path, session_id: str | None, checker: Path,
    *, session_result: dict | None = None,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    stages: list[dict[str, str]] = []
    root = repo.resolve() if repo else None
    git = run(["git", "-C", str(root), "rev-parse", "--show-toplevel"]) if root else None
    if not root or git.returncode != 0 or Path(git.stdout.strip()).resolve() != root:
        return row("github", "Chezmoi repository", "unknown", "Dotfiles-Repository fehlt"), [
            row("local", "Git pulled", "unknown", "Kein gültiger Git-Checkout"),
            row("deployed", "Chezmoi applied", "unknown", "Ohne Quelle nicht prüfbar"),
            session_stage(session_id, codex_home, checker, session_result),
        ]

    remote_sha: str | None = None
    try:
        remote = run(["git", "-C", str(root), "ls-remote", "--exit-code", "origin", "refs/heads/main"], timeout=4)
        if remote.returncode == 0:
            parts = remote.stdout.split()
            if len(parts) == 2 and len(parts[0]) in (40, 64) and parts[1] == "refs/heads/main":
                remote_sha = parts[0]
    except (OSError, subprocess.TimeoutExpired):
        pass
    local_ref = run(["git", "-C", str(root), "rev-parse", "--verify", "refs/heads/main"])
    local_sha = local_ref.stdout.strip() if local_ref.returncode == 0 else ""
    template = "home/dot_codex/AGENTS.md.tmpl"
    source = root / template
    repository = row("github", "Chezmoi repository", "unknown", "Commit-Vergleich nicht möglich")
    if local_sha and remote_sha:
        repository = row("github", "Chezmoi repository", "current" if local_sha == remote_sha else "outdated",
                         f"lokal {local_sha[:8]} · remote {remote_sha[:8]}")

    local_state, local_detail = "unknown", "GitHub-Vergleich nicht möglich"
    if remote_sha and source.is_file():
        upstream = run(["git", "-C", str(root), "show", f"{remote_sha}:{template}"])
        if upstream.returncode:
            # ls-remote can see a commit before the local checkout has fetched it.
            try:
                origin = run(["git", "-C", str(root), "remote", "get-url", "origin"])
                if origin.returncode == 0:
                    with tempfile.TemporaryDirectory() as temporary:
                        clone = run(["git", "clone", "--bare", "--depth=1", "--filter=blob:none",
                                     "--no-local", "--single-branch", "--branch", "main", "--",
                                     origin.stdout.strip(), temporary], cwd=root, timeout=5)
                        if clone.returncode == 0:
                            upstream = run(["git", "-C", temporary, "show", f"{remote_sha}:{template}"])
            except (OSError, subprocess.TimeoutExpired):
                pass
        if upstream.returncode == 0:
            if source.read_bytes() == upstream.stdout.encode("utf-8"):
                local_state, local_detail = "current", "AGENTS.md entspricht GitHub"
            else:
                local_state, local_detail = "outdated", "AGENTS.md weicht von GitHub ab"
    stages.append(row("local", "Git pulled", local_state, local_detail))

    try:
        rendered_file = run(["chezmoi", "--source", str(root / "home"), "cat", str(codex_home / "AGENTS.md")], timeout=3)
        installed = codex_home / "AGENTS.md"
        if rendered_file.returncode or not installed.is_file():
            stages.append(row("deployed", "Chezmoi applied", "unknown", "Ziel oder Template fehlt"))
        elif installed.read_bytes() != rendered_file.stdout.encode("utf-8"):
            stages.append(row("deployed", "Chezmoi applied", "outdated", "Ziel weicht von Quelle ab"))
        else:
            stages.append(row("deployed", "Chezmoi applied", "current", "Ziel stimmt mit Template"))
    except (OSError, subprocess.TimeoutExpired):
        stages.append(row("deployed", "Chezmoi applied", "unknown", "Chezmoi konnte nicht prüfen"))

    stages.append(session_stage(session_id, codex_home, checker, session_result))
    return repository, stages


def find_source() -> Path | None:
    try:
        found = run(["chezmoi", "source-path"], timeout=3)
        if found.returncode == 0 and found.stdout.strip():
            return Path(found.stdout.strip()).parent
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def overall_status(stages: list[dict[str, str]]) -> str:
    states = {stage["status"] for stage in stages}
    return "outdated" if "outdated" in states else "unknown" if "unknown" in states else "current"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", help="Exact ID from the desktop chat deep link")
    parser.add_argument("--repo", type=Path, help="Dotfiles checkout (default: active chezmoi source)")
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser())
    parser.add_argument("--checker", type=Path)
    args = parser.parse_args()
    source = args.repo if args.repo is not None else find_source()
    codex_home = args.codex_home.expanduser()
    checker = args.checker or codex_home / "hooks-json/agents-md-freshness/check.py"
    repository, stages = check(source, codex_home, args.session_id, checker)
    overall = overall_status(stages)
    print(json.dumps({"repository": repository, "overall": overall, "stages": stages}, ensure_ascii=False))


if __name__ == "__main__":
    main()
