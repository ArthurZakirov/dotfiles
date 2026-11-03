#!/usr/bin/env python3
"""Shared read-only five-stage AGENTS.md audit for desktop and Codex hooks.

Exit zero even when a stage is outdated or unverifiable. Never fetch, apply
or modify source files. Missing evidence produces unknown, never false green.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


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
        return row("session", "Codex-Kontext", "unknown", "Keine Codex-Session erkannt")
    elif session_result is None and not checker.is_file():
        return row("session", "Codex-Kontext", "unknown", "Session-Checker fehlt")
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
            return row("session", "Codex-Kontext", status, detail)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return row("session", "Codex-Kontext", "unknown", "Session-Prüfung fehlgeschlagen")

def check(
    repo: Path | None, codex_home: Path, session_id: str | None, checker: Path,
    *, session_result: dict | None = None,
) -> list[dict[str, str]]:
    stages: list[dict[str, str]] = []
    root = repo.resolve() if repo else None
    git = run(["git", "-C", str(root), "rev-parse", "--show-toplevel"]) if root else None
    if not root or git.returncode != 0 or Path(git.stdout.strip()).resolve() != root:
        return [
            row("github", "GitHub main", "unknown", "Dotfiles-Repository fehlt"),
            row("local", "Lokales main", "unknown", "Kein gültiger Git-Checkout"),
            row("generated", "Guidance erzeugt", "unknown", "Ohne Repository nicht prüfbar"),
            row("deployed", "Chezmoi apply", "unknown", "Ohne Quelle nicht prüfbar"),
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
    if remote_sha:
        stages.append(row("github", "GitHub main", "current", remote_sha[:8]))
    else:
        stages.append(row("github", "GitHub main", "unknown", "Remote nicht erreichbar"))

    local_ref = run(["git", "-C", str(root), "rev-parse", "--verify", "refs/heads/main"])
    local_sha = local_ref.stdout.strip() if local_ref.returncode == 0 else ""
    source = root / "home/dot_codex/AGENTS.md.tmpl"
    committed = run(["git", "-C", str(root), "show", "refs/heads/main:home/dot_codex/AGENTS.md.tmpl"])
    local_detail = local_sha[:8] if local_sha else "Lokales main fehlt"
    if local_ref.returncode or committed.returncode or not source.is_file():
        local_state = "outdated"
        local_detail = "Main oder AGENTS.md-Quelle fehlt"
    elif source.read_bytes() != committed.stdout.encode("utf-8"):
        local_state = "outdated"
        local_detail = "Lokale Quelldatei geändert"
    elif not remote_sha:
        local_state = "unknown"
        local_detail = "GitHub-Vergleich nicht möglich"
    elif local_sha != remote_sha:
        local_state = "outdated"
        local_detail = f"lokal {local_sha[:8]} · remote {remote_sha[:8]}"
    else:
        local_state = "current"
    stages.append(row("local", "Lokales main", local_state, local_detail))

    render_script = root / "src/codex-guidance/render.py"
    interpreter = root / ".venv/bin/python"
    if not interpreter.is_file():
        stages.append(row("generated", "Guidance erzeugt", "unknown", "Projekt-Pythonumgebung fehlt"))
    elif not render_script.is_file():
        stages.append(row("generated", "Guidance erzeugt", "unknown", "Renderer fehlt"))
    else:
        try:
            rendered = run([str(interpreter), str(render_script), "--check"], cwd=root, timeout=5)
            if rendered.returncode == 0:
                stages.append(row("generated", "Guidance erzeugt", "current", "Kanonische Quellen stimmen"))
            elif "Outdated Codex guidance:" in rendered.stderr:
                stages.append(row("generated", "Guidance erzeugt", "outdated", "Renderer-Ausgabe veraltet"))
            else:
                stages.append(row("generated", "Guidance erzeugt", "unknown", "Renderer konnte nicht prüfen"))
        except (OSError, subprocess.TimeoutExpired):
            stages.append(row("generated", "Guidance erzeugt", "unknown", "Renderer nicht verfügbar"))

    try:
        rendered_file = run(["chezmoi", "--source", str(root / "home"), "cat", str(codex_home / "AGENTS.md")], timeout=3)
        installed = codex_home / "AGENTS.md"
        if rendered_file.returncode or not installed.is_file():
            stages.append(row("deployed", "Chezmoi apply", "outdated", "Ziel oder Template fehlt"))
        elif installed.read_bytes() != rendered_file.stdout.encode("utf-8"):
            stages.append(row("deployed", "Chezmoi apply", "outdated", "Ziel weicht von Quelle ab"))
        else:
            stages.append(row("deployed", "Chezmoi apply", "current", "Ziel stimmt mit Template"))
    except (OSError, subprocess.TimeoutExpired):
        stages.append(row("deployed", "Chezmoi apply", "unknown", "Chezmoi konnte nicht prüfen"))

    stages.append(session_stage(session_id, codex_home, checker, session_result))
    return stages


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
    stages = check(source, codex_home, args.session_id, checker)
    overall = overall_status(stages)
    print(json.dumps({"overall": overall, "stages": stages}, ensure_ascii=False))


if __name__ == "__main__":
    main()
