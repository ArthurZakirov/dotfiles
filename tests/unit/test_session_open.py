"""Public contracts for context-aware search and Warp/Chrome opening."""
from __future__ import annotations

import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sqlite3
import subprocess
import sys
import tomllib
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "home/dot_local/lib"))

from find_gpt_session.context import ContextError, from_workspace, from_browser_url
from find_gpt_session.core import SearchRequest, SessionHit, SearchResponse
from find_gpt_session.launch import (
    ChromeTabLauncher, SessionOpener, WarpTabLauncher, LaunchError,
    verified_chat_url,
)


CODEX_ID = "11111111-2222-4333-8444-555555555555"
OTHER_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
CHAT_URL = "https://chatgpt.com/c/" + CODEX_ID


def test_workspace_context_uses_branch_or_repo(tmp_path):
    repo = tmp_path / "demo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)

    assert from_workspace(str(repo)) == SearchRequest.create("repo", "demo")
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", "feat/a"], check=True)
    assert from_workspace(str(repo)) == SearchRequest.create("branch", "feat/a")


@pytest.mark.parametrize(("link", "expected_kind", "expected_value"), [
    ("https://github.com/org/demo/pull/67#discussion-r1", "pr",
     "https://github.com/org/demo/pull/67"),
    ("https://bitbucket.org/team/demo/pull-requests/9#comment-3", "pr",
     "https://bitbucket.org/team/demo/pull-requests/9"),
    ("https://github.com/org/demo/tree/feature-name", "branch", "feature-name"),
    ("https://github.com/org/demo/tree/feature/name/src/file.py", "repo", "demo"),
    ("https://github.com/org/demo", "repo", "demo"),
])
def test_browser_context(link, expected_kind, expected_value):
    result = from_browser_url(link)
    assert (result.kind, result.value) == (expected_kind, expected_value)


def test_browser_context_rejects_other_domains():
    with pytest.raises(ContextError):
        from_browser_url("https://malicious.example/github.com/org/demo/pull/2")


def test_warp_launcher_writes_tab_config_with_resume_command(tmp_path):
    called = []

    def run(args, **kwargs):
        called.append(args)
        return subprocess.CompletedProcess(args, 0)

    codex = tmp_path / ".codex"
    codex.mkdir()
    con = sqlite3.connect(codex / "state_5.sqlite")
    con.execute("CREATE TABLE threads (id TEXT, cwd TEXT)")
    con.execute("INSERT INTO threads VALUES (?,?)", (CODEX_ID, str(tmp_path)))
    con.commit()
    con.close()
    launcher = WarpTabLauncher(tmp_path, runner=run)

    launcher.open_session(CODEX_ID)

    configs = list((tmp_path / ".warp/tab_configs").glob("find_gpt_session_*.toml"))
    assert len(configs) == 1
    data = tomllib.loads(configs[0].read_text())
    assert data["panes"][0]["commands"] == ["codex resume " + CODEX_ID]
    assert data["panes"][0]["directory"] == str(tmp_path)
    assert called[0][0] == "/usr/bin/open"
    assert called[0][1].startswith("warp://tab_config/find_gpt_session_")
    assert configs[0].stat().st_mode & 0o077 == 0


def test_codex_launcher_never_runs_unverified_commands(tmp_path):
    launcher = WarpTabLauncher(tmp_path, runner=lambda *a, **k: None)
    with pytest.raises(LaunchError):
        launcher.open_session("; rm -rf ~")
    assert not (tmp_path / ".warp").exists()


def test_chrome_launcher_uses_one_window_for_all_urls():
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    launcher = ChromeTabLauncher(runner=run)
    launcher.open_urls([CHAT_URL, "https://chatgpt.com/c/" + OTHER_ID])

    assert len(calls) == 1
    assert calls[0][0:2] == ["/usr/bin/osascript", "-e"]
    assert "front window" in calls[0][2]
    assert calls[0][3:] == [CHAT_URL, "https://chatgpt.com/c/" + OTHER_ID]


@pytest.mark.parametrize("url", [
    "https://evil.example/c/" + CODEX_ID,
    "http://chatgpt.com/c/" + CODEX_ID,
    "https://chatgpt.com/share/" + CODEX_ID,
    "https://chatgpt.com/c/not-a-uuid",
    "https://chatgpt.com/c/" + CODEX_ID + "/deleted",
])
def test_unverified_chat_url_is_refused(url):
    assert verified_chat_url(url) is None


def test_session_open_all_results_deduplicates_and_skips_unverified():
    class FakeWarp:
        ids = []

        def open_session(self, session_id):
            self.ids.append(session_id)

    class FakeChrome:
        urls = []

        def open_urls(self, urls):
            self.urls.extend(urls)

    warp, chrome = FakeWarp(), FakeChrome()
    hits = [
        SessionHit("codex", CODEX_ID, "Work", None, 100, "Git"),
        SessionHit("codex", CODEX_ID, "Work duplicate", None, 90, "Git"),
        SessionHit("chatgpt", CODEX_ID, "Chat", CHAT_URL, 70, "Web"),
        SessionHit("chatgpt", CODEX_ID, "Chat duplicate", CHAT_URL, 60, "Web"),
        SessionHit("chatgpt", None, "Unverified suggestion", None, 20, "Web"),
    ]

    result = SessionOpener(warp=warp, chrome=chrome).open(hits)

    assert warp.ids == [CODEX_ID]
    assert chrome.urls == [CHAT_URL]
    assert len(result.dispatched) == 2
    assert len(result.skipped) == 1
    assert result.errors == []


def test_cli_open_context_invokes_search_then_open_without_extra_cli(capsys):
    script = ROOT / "home/dot_local/bin/executable_find-gpt-session"
    loader = SourceFileLoader("find_gpt_session_open_cli_test", str(script))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec
    cli = importlib.util.module_from_spec(spec)
    loader.exec_module(cli)

    class FakeSearch:
        def __init__(self, providers):
            pass

        def search(self, request, limit):
            assert request.kind == "pr"
            assert request.ui_term == "pull/67"
            hits = [
                SessionHit("codex", CODEX_ID, "Codex", None, 80, "Git"),
                SessionHit("chatgpt", CODEX_ID, "Chat", CHAT_URL, 70, "Chat"),
            ]
            return SearchResponse(request, ("codex", "safari"), hits, [], ["safari"])

    class FakeOpener:
        def open(self, hits):
            from find_gpt_session.launch import OpenResult
            return OpenResult(requested=len(hits), dispatched=[
                {"provider": hit.provider, "destination": "new-tab"}
                for hit in hits
            ])

    with patch.object(cli, "create_providers", return_value=[]), \
         patch.object(cli, "FindSessions", FakeSearch), \
         patch.object(cli, "SessionOpener", FakeOpener):
        rc = cli.main(["--open", "--context-url",
                       "https://github.com/org/demo/pull/67", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["opening"]["requested"] == 2
    assert len(payload["opening"]["dispatched"]) == 2



def test_codex_results_survive_safari_timeout():
    from find_gpt_session.core import FindSessions, ProviderResult, SearchRequest

    class Codex:
        name = "codex"

        def search(self, request, limit):
            return ProviderResult([
                SessionHit("codex", CODEX_ID, "Recovered session", None, 88,
                           "Codex text", "codex resume " + CODEX_ID),
            ], complete=True)

    class Safari:
        name = "safari"

        def search(self, request, limit):
            raise TimeoutError("background Safari search timed out")

    result = FindSessions([Codex(), Safari()]).search(
        SearchRequest.create("text", "cleanup"), 10
    )
    assert len(result.hits) == 1
    assert result.hits[0].provider == "codex"
    assert result.incomplete_providers == ["safari"]
    assert "timed out" in " ".join(result.warnings)
