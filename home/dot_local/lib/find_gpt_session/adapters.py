"""Outbound adapters. All browser and Codex implementation details stay here."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from .core import ProviderResult, SearchRequest, SessionHit
from .codex_text import CodexTranscriptSearcher


def session_find_command() -> str:
    """Use the backend installed alongside this package, including GUI PATHs."""
    return str(Path(__file__).resolve().parents[2] / "bin/session-find")


def run_json(argv: list[str], timeout: int = 50) -> dict:
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("search timed out") from exc
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip()[:350] or
                           f"exit code {result.returncode}")
    try:
        return json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("backend returned invalid JSON") from exc


class CodexProvider:
    name = "codex"

    def search(self, request: SearchRequest, limit: int) -> ProviderResult:
        if request.kind == "text":
            return CodexTranscriptSearcher().search(request.value, limit)
        result = run_json([session_find_command(), f"--{request.kind}", request.value,
                           "--limit", str(limit), "--json"])
        hits = [
            SessionHit("codex", item.get("session_id"),
                       item.get("title") or "(untitled)", None,
                       int(item.get("score", 0)),
                       item.get("evidence_strength", "Codex native history"),
                       item.get("resume_command"))
            for item in result.get("results", [])
        ]
        return ProviderResult(hits, result.get("stats", {}).get("warnings", []),
                              complete=bool(result.get("stats", {}).get("history_available")))


class DesktopProvider:
    name = "desktop"

    def search(self, request: SearchRequest, limit: int) -> ProviderResult:
        # Existing desktop AX adapter already lives in session-find;
        # results are suggestions, not verified permalinks.
        result = run_json([session_find_command(), "--chatgpt-query", request.ui_term,
                           "--limit", str(limit), "--json"])
        hits = [
            SessionHit("chatgpt", None, item.get("title") or "(untitled)",
                       None, 30, item.get("evidence", "Desktop search suggestion"))
            for item in result.get("chatgpt_results", [])
        ]
        return ProviderResult(hits, result.get("chatgpt_search", {}).get("warnings", []))


class BrowserProvider:
    """Live, non-persistent ChatGPT UI search; no credentials or cookie scraping."""

    def __init__(self, name: str, source: Path | None = None,
                 executable: Path | None = None):
        if name not in {"safari", "chrome"}:
            raise ValueError("Browser must be safari or chrome")
        self.name = name
        local = Path(__file__).resolve().parents[2]
        self.source = source or (local / "share/find-gpt-session/ui.swift")
        self.executable = executable or Path.home() / ".cache/find-gpt-session/ui-ax"

    def _ready_executable(self) -> Path:
        if not self.source.exists():
            raise RuntimeError("UI adapter source missing; apply managed Dotfiles")
        self.executable.parent.mkdir(parents=True, exist_ok=True)
        if (not self.executable.exists() or
                self.executable.stat().st_mtime < self.source.stat().st_mtime):
            temp = self.executable.with_suffix(".pending")
            try:
                result = subprocess.run(["swiftc", "-O", str(self.source), "-o", str(temp)],
                                        capture_output=True, text=True, timeout=100)
                if result.returncode != 0:
                    raise RuntimeError("Swift compilation failed: " + result.stderr[-500:])
                temp.replace(self.executable)
            finally:
                temp.unlink(missing_ok=True)
        return self.executable

    def prepare(self) -> bool:
        """Prime an already-running Safari ChatGPT tab without searching.

        Uses the same compiled Accessibility adapter as normal search.
        Hammerspoon calls this opportunistically when its configuration loads;
        a failed warmup never disables normal on-demand search.
        """
        if self.name != "safari":
            raise ValueError("Only the dedicated Safari adapter can be primed")
        data = run_json([str(self._ready_executable()), "--prepare-safari"], timeout=18)
        return data.get("prepared") is True

    def search(self, request: SearchRequest, limit: int) -> ProviderResult:
        data = run_json([str(self._ready_executable()), self.name, request.ui_term,
                         str(min(limit, 12))], timeout=20 + 20 * min(limit, 12))
        hits = [
            SessionHit("chatgpt", item.get("sessionId"),
                       item.get("title") or "(untitled)", item.get("url"),
                       70, item.get("evidence", "Visible ChatGPT search result"))
            for item in data.get("results", [])
        ]
        warnings = list(data.get("warnings", []))
        if not hits and warnings:
            warnings.append("No verified URL; not a confirmed zero-availability result")
        return ProviderResult(hits, warnings, complete=False)


AVAILABLE = ("codex", "safari", "chrome", "desktop")


def create_providers(names: list[str]):
    registry = {
        "codex": CodexProvider,
        "safari": lambda: BrowserProvider("safari"),
        "chrome": lambda: BrowserProvider("chrome"),
        "desktop": DesktopProvider,
    }
    expanded = AVAILABLE if "all" in names else tuple(dict.fromkeys(names))
    return [registry[name]() for name in expanded]
