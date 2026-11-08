"""Contract tests for native Codex text-search infrastructure and global CLI."""
from __future__ import annotations

import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "home/dot_local/lib"))

from find_gpt_session.adapters import CodexProvider
from find_gpt_session.codex_text import CodexTranscriptSearcher
from find_gpt_session.core import FindSessions, ProviderResult, SearchRequest, SessionHit


def populate_codex_fixture(home: Path) -> None:
    state = sqlite3.connect(home / "state_5.sqlite")
    state.execute(
        "CREATE TABLE threads (id TEXT, title TEXT, first_user_message TEXT, "
        "preview TEXT, created_at INTEGER)"
    )
    state.executemany(
        "INSERT INTO threads VALUES(?,?,?,?,?)",
        [
            ("codex-title", "Worktree cleanup investigation", "", "", 200),
            ("codex-messages", "Other topic", "", "", 100),
            ("codex-utf8", "German conversation", "", "", 50),
            ("codex-tool", "Unrelated session", "", "", 20),
        ],
    )
    state.commit()
    state.close()

    history = sqlite3.connect(home / "thread_history_1.sqlite")
    history.execute("CREATE TABLE thread_items (thread_id TEXT, item_type TEXT, item_json TEXT)")
    rows = [
        ("codex-messages", "userMessage",
         {"type": "userMessage", "content": [{"type": "text", "text": "worktree"}]}),
        ("codex-messages", "agentMessage",
         {"type": "agentMessage", "text": "The cleanup plan has steps."}),
        ("codex-utf8", "userMessage",
         {"type": "userMessage", "content": [{"type": "text", "text": "ÄNDERUNGEN"}]}),
        ("codex-tool", "commandExecution",
         {"type": "commandExecution", "command": "worktree cleanup"}),
        ("codex-tool", "reasoning", {"type": "reasoning", "text": "worktree cleanup"}),
    ]
    history.executemany(
        "INSERT INTO thread_items VALUES(?,?,?)",
        [(sid, kind, json.dumps(payload, ensure_ascii=False)) for sid, kind, payload in rows],
    )
    history.commit()
    history.close()


def test_codex_keyword_search_reads_titles_and_cross_message_terms(tmp_path):
    populate_codex_fixture(tmp_path)

    result = CodexTranscriptSearcher(tmp_path).search("worktree cleanup", 10)

    assert result.complete is True
    assert [hit.session_id for hit in result.hits] == ["codex-title", "codex-messages"]
    assert result.hits[0].score > result.hits[1].score
    assert all(hit.resume_command == f"codex resume {hit.session_id}"
               for hit in result.hits)
    assert all(hit.provider == "codex" for hit in result.hits)


def test_codex_keyword_search_is_unicode_case_insensitive(tmp_path):
    populate_codex_fixture(tmp_path)

    result = CodexTranscriptSearcher(tmp_path).search("änderungen", 10)

    assert [hit.session_id for hit in result.hits] == ["codex-utf8"]


def test_codex_search_never_matches_only_tool_outputs_or_private_reasoning(tmp_path):
    populate_codex_fixture(tmp_path)

    result = CodexTranscriptSearcher(tmp_path).search("worktree cleanup", 10)

    assert "codex-tool" not in [hit.session_id for hit in result.hits]


def test_codex_no_state_is_explicit_failure(tmp_path):
    with pytest.raises(FileNotFoundError, match="Codex session metadata"):
        CodexTranscriptSearcher(tmp_path).search("cleanup", 10)


def test_codex_provider_text_uses_native_search_and_not_legacy_binary():
    request = SearchRequest.create("text", "worktree cleanup")
    provider_response = ProviderResult(
        hits=[SessionHit("codex", "id", "Task", None, 90, "user text",
                         "codex resume id")],
        complete=True,
    )
    with patch("find_gpt_session.adapters.CodexTranscriptSearcher") as searcher, \
         patch("find_gpt_session.adapters.run_json") as legacy:
        searcher.return_value.search.return_value = provider_response
        actual = CodexProvider().search(request, 6)

    assert actual == provider_response
    searcher.return_value.search.assert_called_once_with("worktree cleanup", 6)
    legacy.assert_not_called()


def test_default_global_cli_merges_codex_and_chatgpt_sources(capsys):
    script = ROOT / "home/dot_local/bin/executable_find-gpt-session"
    loader = SourceFileLoader("find_gpt_session_global_cli", str(script))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)

    class FakeProvider:
        def __init__(self, name, hits, complete=True):
            self.name, self.hits, self.complete = name, hits, complete

        def search(self, request, limit):
            assert request.kind == "text"
            assert request.value == "worktree cleanup"
            return ProviderResult(self.hits, complete=self.complete)

    codex = FakeProvider("codex", [
        SessionHit("codex", "c1", "Codex conversation", None, 95,
                   "Codex text", "codex resume c1")
    ])
    safari = FakeProvider("safari", [
        SessionHit("chatgpt", "g1", "ChatGPT conversation",
                   "https://chatgpt.com/c/example", 70, "Browser message")
    ], complete=False)
    with patch.object(module, "create_providers", return_value=[codex, safari]) as factory:
        result = module.main(["search", "worktree cleanup", "--json"])

    assert result == 0
    factory.assert_called_once_with(["codex", "safari"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["providers"] == ["codex", "safari"]
    assert {hit["provider"] for hit in payload["results"]} == {"codex", "chatgpt"}
    assert payload["search_status"] == "partial"
    assert any(hit["resume_command"] for hit in payload["results"])
    assert any(hit["url"] for hit in payload["results"])


def test_global_limit_reserves_results_from_both_products():
    class Provider:
        def __init__(self, name, hits):
            self.name, self.hits = name, hits

        def search(self, request, limit):
            return ProviderResult(self.hits, complete=True)

    codex = Provider("codex", [
        SessionHit("codex", f"codex-{i}", f"Codex {i}", None, 120 - i,
                   "title match", f"codex resume codex-{i}")
        for i in range(8)
    ])
    chatgpt = Provider("safari", [
        SessionHit("chatgpt", "chat-1", "Matching ChatGPT session",
                   "https://chatgpt.com/c/placeholder", 70, "browser match")
    ])
    output = FindSessions([codex, chatgpt]).search(
        SearchRequest.create("text", "worktree cleanup"), limit=3
    )

    assert len(output.hits) == 3
    assert [hit.provider for hit in output.hits].count("chatgpt") == 1
    assert [hit.provider for hit in output.hits].count("codex") == 2
    assert output.hits == sorted(output.hits, key=lambda h: -h.score)
