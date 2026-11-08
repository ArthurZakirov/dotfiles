"""Read-only full-text search across locally recorded Codex conversations.

This is a Codex infrastructure adapter, not a second search core or index.
Only titles, previews, and user/agent messages are examined; tool outputs,
private reasoning and arbitrary file contents are deliberately excluded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sqlite3

from .core import ProviderResult, SessionHit


@dataclass
class _Candidate:
    session_id: str
    title: str
    created_at: int
    observed: set[str] = field(default_factory=set)
    best_score: int = 0
    evidence: str = ""

    def consider(self, text: str, words: tuple[str, ...], score: int, source: str) -> None:
        if not text:
            return
        folded = text.casefold()
        matches = {word for word in words if word in folded}
        if not matches:
            return
        self.observed.update(matches)
        if len(matches) == len(words) and score > self.best_score:
            self.best_score = score
            self.evidence = f"Codex {source} contains all search keywords"

    def hit(self, words: tuple[str, ...]) -> SessionHit | None:
        if not all(word in self.observed for word in words):
            return None
        return SessionHit(
            provider="codex",
            session_id=self.session_id,
            title=self.title or "(untitled)",
            url=None,
            score=self.best_score or 40,
            evidence=self.evidence or "Keywords mentioned across Codex conversation messages",
            resume_command=f"codex resume {self.session_id}",
        )


def _connect_ro(path: Path) -> sqlite3.Connection | None:
    if not path.is_file():
        return None
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    connection.execute("PRAGMA query_only=ON")
    return connection


class CodexTranscriptSearcher:
    """Search existing Codex SQLite without adding a persistent search database."""

    def __init__(self, codex_home: Path | None = None):
        self.home = Path(codex_home or os.environ.get("CODEX_HOME") or
                         (Path.home() / ".codex"))

    def search(self, query: str, limit: int) -> ProviderResult:
        words = tuple(dict.fromkeys(query.casefold().split()))
        if not words:
            raise ValueError("Codex search text must not be empty")
        state = _connect_ro(self.home / "state_5.sqlite")
        if state is None:
            raise FileNotFoundError(f"Codex session metadata not found in {self.home}")
        candidates: dict[str, _Candidate] = {}
        history = None
        warnings: list[str] = []
        try:
            for thread_id, title, first_message, preview, created_at in state.execute(
                "SELECT id, title, first_user_message, preview, created_at FROM threads"
            ):
                candidate = _Candidate(thread_id, title or "", int(created_at or 0))
                candidate.consider(title or "", words, 100, "session title")
                candidate.consider(first_message or "", words, 90, "first user message")
                candidate.consider(preview or "", words, 75, "session preview")
                candidates[thread_id] = candidate

            history = _connect_ro(self.home / "thread_history_1.sqlite")
            if history is None:
                warnings.append("Codex message history unavailable; searched titles/previews only")
            else:
                # The SQLite predicate excludes the 28k+ reasoning, tool and
                # execution items. One narrow term limits Python JSON parsing
                # without creating or updating an index. Non-ASCII terms use
                # Python casefold throughout (SQLite lower is ASCII-only).
                statement = (
                    "SELECT thread_id, item_type, item_json FROM thread_items "
                    "WHERE item_type IN ('userMessage','agentMessage')"
                )
                params: tuple[str, ...] = ()
                if all(word.isascii() for word in words):
                    # OR is important: keywords may occur in different turns.
                    statement += " AND (" + " OR ".join(
                        "instr(lower(item_json), ?) > 0" for _ in words
                    ) + ")"
                    params = words
                for thread_id, item_type, serialized in history.execute(statement, params):
                    candidate = candidates.get(thread_id)
                    if candidate is None:
                        continue
                    try:
                        payload = json.loads(serialized)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if item_type == "userMessage":
                        message = " ".join(
                            part.get("text", "") for part in payload.get("content", [])
                            if isinstance(part, dict) and isinstance(part.get("text"), str)
                            and part.get("type") == "text"
                        )
                        candidate.consider(message, words, 88, "user message")
                    elif item_type == "agentMessage":
                        message = payload.get("text")
                        if isinstance(message, str):
                            candidate.consider(message, words, 68, "assistant message")

            # Do not misrepresent matches in separated messages as an exact
            # phrase match; their evidence explicitly says "across".
            ranked = [
                (hit, candidate.created_at)
                for candidate in candidates.values()
                if (hit := candidate.hit(words)) is not None
            ]
            ranked.sort(key=lambda item: (
                -item[0].score, -item[1], item[0].session_id or ""
            ))
            return ProviderResult(
                hits=[hit for hit, _ in ranked[:limit]],
                warnings=warnings,
                complete=history is not None,
            )
        finally:
            state.close()
            if history is not None:
                history.close()
