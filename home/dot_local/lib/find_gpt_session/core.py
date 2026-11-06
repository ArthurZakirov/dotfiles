"""Domain models and a single search use case shared by all providers."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
import re

_PR_TYPES = frozenset({"pull", "pull-requests"})
_COMMIT = re.compile(r"[a-f0-9]{7,40}", re.I)
_JIRA = re.compile(r"[A-Z][A-Z0-9_]*-\d+", re.I)


@dataclass(frozen=True)
class SearchRequest:
    kind: str
    value: str

    @classmethod
    def create(cls, kind: str, raw: str) -> "SearchRequest":
        raw = raw.strip()
        if not raw:
            raise ValueError("Search value cannot be empty")
        if kind == "pr":
            parsed = urlsplit(raw)
            parts = parsed.path.strip("/").split("/")
            if (parsed.scheme != "https" or not parsed.hostname or
                    len(parts) < 4 or parts[2] not in _PR_TYPES or
                    not parts[3].isdigit()):
                raise ValueError("--pr requires a GitHub or Bitbucket HTTPS pull-request URL")
            return cls(kind, f"https://{parsed.hostname.lower()}/{'/'.join(parts[:4])}")
        if kind == "commit" and not _COMMIT.fullmatch(raw):
            raise ValueError("--commit requires a 7–40 character Git SHA prefix")
        if kind == "jira":
            raw = raw.upper()
            if not _JIRA.fullmatch(raw):
                raise ValueError("--jira requires an issue key such as DCP-123")
        if kind == "worktree":
            raw = str(Path(raw).expanduser().resolve())
        return cls(kind, raw)

    @property
    def ui_term(self) -> str:
        """One visible ChatGPT search term; no claim of semantic fuzzy retrieval."""
        if self.kind == "pr":
            parts = urlsplit(self.value).path.strip("/").split("/")
            return f"{parts[2]}/{parts[3]}"
        if self.kind == "repo":
            return self.value.rstrip("/").split("/")[-1].removesuffix(".git")
        if self.kind == "worktree":
            return Path(self.value).name
        return self.value


@dataclass(frozen=True)
class SessionHit:
    provider: str
    session_id: str | None
    title: str
    url: str | None
    score: int
    evidence: str
    resume_command: str | None = None

    def asdict(self) -> dict:
        return {
            "provider": self.provider, "session_id": self.session_id,
            "title": self.title, "url": self.url, "score": self.score,
            "evidence": self.evidence, "resume_command": self.resume_command,
        }


@dataclass
class ProviderResult:
    hits: list[SessionHit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    complete: bool = False


class SessionProvider(Protocol):
    name: str

    def search(self, request: SearchRequest, limit: int) -> ProviderResult:
        ...


@dataclass
class SearchResponse:
    request: SearchRequest
    providers: tuple[str, ...]
    hits: list[SessionHit]
    warnings: list[str]
    incomplete_providers: list[str]

    def asdict(self) -> dict:
        return {
            "query": {"type": self.request.kind, "value": self.request.value,
                      "ui_term": self.request.ui_term},
            "providers": list(self.providers), "total": len(self.hits),
            "results": [hit.asdict() for hit in self.hits],
            "warnings": self.warnings,
            "incomplete_providers": self.incomplete_providers,
        }


class FindSessions:
    """Pure application service: query → adapters → normalized, ranked results."""

    def __init__(self, providers: list[SessionProvider]):
        self.providers = providers

    def search(self, request: SearchRequest, limit: int = 25) -> SearchResponse:
        hits: dict[tuple[str, str], SessionHit] = {}
        warnings: list[str] = []
        incomplete: list[str] = []
        for provider in self.providers:
            try:
                response = provider.search(request, limit)
            except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
                warnings.append(f"{provider.name}: {exc}")
                incomplete.append(provider.name)
                continue
            if not response.complete:
                incomplete.append(provider.name)
            warnings.extend(f"{provider.name}: {warning}" for warning in response.warnings)
            for hit in response.hits:
                # Providers may see the same conversation from several surfaces.
                key = (hit.provider, hit.session_id or hit.title)
                old = hits.get(key)
                if old is None or (bool(hit.url), hit.score) > (bool(old.url), old.score):
                    hits[key] = hit
        ranked = sorted(hits.values(), key=lambda hit: (
            -hit.score, hit.provider, hit.title.casefold()))
        return SearchResponse(request, tuple(p.name for p in self.providers),
                              ranked[:limit], warnings, incomplete)
