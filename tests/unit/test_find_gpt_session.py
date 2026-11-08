"""Unit and CLI contract tests for the provider-neutral search use case."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "home/dot_local/lib"))
from find_gpt_session.core import (
    FindSessions, ProviderResult, SearchRequest, SessionHit,
)
from find_gpt_session.adapters import BrowserProvider, CodexProvider, DesktopProvider, create_providers


class FakeProvider:
    name = "safari"

    def __init__(self, results, complete=False):
        self.results = results
        self.complete = complete
        self.called = []

    def search(self, request, limit):
        self.called.append((request, limit))
        return ProviderResult(self.results, complete=self.complete)


def test_url_canonicalization_and_ui_search_term():
    q = SearchRequest.create(
        "pr", "https://github.com/ArthurZakirov/dotfiles/pull/67#discussion"
    )
    assert q.value == "https://github.com/ArthurZakirov/dotfiles/pull/67"
    assert q.ui_term == "pull/67"


def test_repo_branch_and_jira_term():
    assert SearchRequest.create("repo", "git@github.com:Org/Project.git").ui_term == "Project"
    assert SearchRequest.create("branch", "feat/hello").ui_term == "feat/hello"
    assert SearchRequest.create("jira", "dcp-123").ui_term == "DCP-123"


def test_invalid_sha_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="Git SHA"):
        SearchRequest.create("commit", "not-a-commit")


def test_combined_core_ranks_and_preserves_links():
    first = FakeProvider([
        SessionHit("chatgpt", "abc", "Chat one", "https://chatgpt.com/c/abc", 70, "UI"),
    ])
    second = FakeProvider([
        SessionHit("codex", "xyz", "Codex work", None, 80, "git activity",
                   "codex resume xyz"),
    ], complete=True)
    output = FindSessions([first, second]).search(SearchRequest.create("text", "worktree"))
    assert [h.provider for h in output.hits] == ["codex", "chatgpt"]
    assert output.hits[1].url == "https://chatgpt.com/c/abc"
    assert output.incomplete_providers == ["safari"]
    assert first.called[0][0].value == "worktree"


def test_duplicate_sessions_choose_verified_url():
    no_link = FakeProvider([
        SessionHit("chatgpt", "same", "Chat", None, 40, "suggestion")
    ])
    linked = FakeProvider([
        SessionHit("chatgpt", "same", "Chat", "https://chatgpt.com/c/same", 30, "verified")
    ])
    linked.name = "chrome"
    output = FindSessions([no_link, linked]).search(SearchRequest.create("text", "chat"))
    assert len(output.hits) == 1
    assert output.hits[0].url


def test_provider_failure_explicitly_warns():
    class Broken:
        name = "safari"

        def search(self, request, limit):
            raise RuntimeError("No ChatGPT tab")

    output = FindSessions([Broken()]).search(SearchRequest.create("pr", "https://github.com/a/b/pull/4"))
    assert output.hits == []
    assert output.incomplete_providers == ["safari"]
    assert "No ChatGPT tab" in output.warnings[0]


def test_codex_adapter_uses_native_readonly_search():
    raw = {
        "results": [{"session_id": "abc", "title": "Work", "score": 80,
                     "resume_command": "codex resume abc", "evidence_strength": "file-activity"}],
        "stats": {"history_available": True, "warnings": []}
    }
    with patch("find_gpt_session.adapters.run_json", return_value=raw) as runner:
        result = CodexProvider().search(SearchRequest.create("branch", "my-branch"), 5)
    assert runner.call_args.args[0] == [
        str(ROOT / "home/dot_local/bin/session-find"), "--branch", "my-branch", "--limit", "5", "--json"
    ]
    assert result.complete
    assert result.hits[0].resume_command == "codex resume abc"


def test_browser_adapter_uses_compiled_swift_program():
    browser = BrowserProvider("safari", source=Path("/tmp/fake.swift"),
                              executable=Path("/tmp/fake-ax"))
    with patch.object(browser, "_ready_executable", return_value=Path("/tmp/fake-ax")), \
         patch("find_gpt_session.adapters.run_json", return_value={
             "results": [{"sessionId": "one", "title": "Chat", "url": "https://chatgpt.com/c/one"}],
             "warnings": [], "provider": "safari"
         }) as runner:
        result = browser.search(SearchRequest.create("text", "cleanup"), 3)
    assert result.hits[0].url == "https://chatgpt.com/c/one"
    assert runner.call_args.args[0] == ["/tmp/fake-ax", "safari", "cleanup", "3"]


def test_default_provider_selections_are_distinct():
    assert [p.name for p in create_providers(["codex", "safari"])] == ["codex", "safari"]
    assert [p.name for p in create_providers(["all"])] == [
        "codex", "safari", "chrome", "desktop"
    ]


def test_cli_contract_json():
    script = ROOT / "home/dot_local/bin/executable_find-gpt-session"
    # Executable has no .py extension; use a loader without deprecated load_module.
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("find_gpt_session_cli", str(script))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    provider = FakeProvider([SessionHit("chatgpt", "abc", "Found", "https://chatgpt.com/c/abc",
                                       70, "UI")])
    with patch.object(module, "create_providers", return_value=[provider]), \
         patch("sys.stdout") as out:
        assert module.main(["--pr", "https://github.com/a/b/pull/4", "--provider", "safari",
                            "--json"]) == 0
    print_calls = [c.args[0] for c in out.write.call_args_list if c.args and c.args[0].strip()]
    payload = json.loads("".join(print_calls))
    assert payload["query"]["ui_term"] == "pull/4"
    assert payload["results"][0]["session_id"] == "abc"


def test_incomplete_zero_results_are_not_confirmed_absence():
    class Unavailable:
        name = "safari"

        def search(self, request, limit):
            return ProviderResult([], warnings=["Browser UI not accessible"], complete=False)

    response = FindSessions([Unavailable()]).search(SearchRequest.create("text", "pull/67"))
    assert not response.hits
    assert response.asdict()["search_status"] == "incomplete"
    assert response.incomplete_providers == ["safari"]


def test_cli_incomplete_search_returns_error_not_false_zero(capsys):
    from importlib.machinery import SourceFileLoader
    import importlib.util
    script = ROOT / "home/dot_local/bin/executable_find-gpt-session"
    loader = SourceFileLoader("find_gpt_session_incomplete_cli", str(script))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)

    class Unavailable:
        name = "safari"

        def search(self, request, limit):
            return ProviderResult([], warnings=["UI unavailable"], complete=False)

    with patch.object(module, "create_providers", return_value=[Unavailable()]):
        rc = module.main(["search", "pull/67", "--provider", "safari"])
    stdout, stderr = capsys.readouterr()
    assert rc == 2
    assert "Search incomplete" in stdout
    assert "Found 0 sessions" not in stdout
    assert "UI unavailable" in stderr
