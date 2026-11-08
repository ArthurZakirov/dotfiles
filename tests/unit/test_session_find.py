"""Offline contract tests for the read-only session search core."""
import argparse
import io
import json
import os
import subprocess
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import importlib.machinery
import importlib.util
import sys

SCRIPT = Path(__file__).resolve().parents[2] / "home/dot_local/bin/executable_session-find"
loader = importlib.machinery.SourceFileLoader("session_find", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)
CodexSearcher = module.CodexSearcher
SearchQuery = module.SearchQuery
canonical_pr = module.canonical_pr
canonical_remote = module.canonical_remote
main = module.main


class SearchFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.codex = self.home / ".codex"
        self.codex.mkdir()
        self.state = sqlite3.connect(self.codex / "state_5.sqlite")
        self.history = sqlite3.connect(self.codex / "thread_history_1.sqlite")
        self.state.executescript("""
            CREATE TABLE threads(id TEXT, title TEXT, cwd TEXT, git_branch TEXT,
                git_origin_url TEXT, git_sha TEXT, created_at INTEGER,
                first_user_message TEXT, preview TEXT);
            CREATE TABLE thread_attachments(thread_id TEXT, attachment_type TEXT, payload TEXT);
            CREATE TABLE thread_spawn_edges(parent_thread_id TEXT, child_thread_id TEXT);
        """)
        self.history.executescript("""
            CREATE TABLE thread_items(thread_id TEXT, item_type TEXT, item_json TEXT);
        """)
        h = str(self.home)
        self.repo_a = f"{h}/Repos/personal/dotfiles"
        self.repo_a_worktree = f"{h}/Repos/personal/dotfiles.worktrees/feat-cross-repo"
        self.repo_b = f"{h}/Repos/personal/AgentDesk"
        self.state.executemany("INSERT INTO threads VALUES (?,?,?,?,?,?,?,?,?)", [
            ("session-A", "Multi repo implementation", h, None, None, None, 100, None, None),
            ("session-B", "Branch feature", self.repo_a, "feat/cross-repo", "git@github.com:ArthurZakirov/dotfiles.git", "abcdef1234567890", 200, None, None),
            ("session-C", "PR task", f"{h}/Documents/Codex/random", None, None, None, 300, None, None),
            ("session-D", "DCP-9712 pipeline", h, None, None, None, 400, None, None),
            ("session-E", "Unrelated", self.repo_b, None, "git@github.com:ArthurZakirov/AgentDesk.git", None, 500, None, None),
            ("session-F", "Subagent", h, None, None, None, 600, None, None),
        ])
        self.state.execute("INSERT INTO thread_attachments VALUES (?,?,?)", ("session-C", "pull_request", json.dumps({"url":"https://github.com/ArthurZakirov/dotfiles/pull/2"})))
        self.state.execute("INSERT INTO thread_spawn_edges VALUES (?,?)", ("session-C", "session-F"))
        self.event("session-A", "fileChange", {"changes": [{"path": self.repo_a_worktree + "/home/x.py"}, {"path": self.repo_b + "/src/y.py"}]})
        self.event("session-A", "commandExecution", {"cwd": self.repo_b, "command":"git status --short"})
        self.event("session-A", "userMessage", {"content": [{"text":"Work on DCP-9712 on both repos"}]})
        self.event("session-B", "fileChange", {"changes": [{"path": self.repo_a + "/hello.py"}]})
        self.event("session-D", "agentMessage", {"text":"DCP-9712 is in the backlog"})
        self.state.commit()
        self.history.commit()
        self.state.close()
        self.history.close()
        self.searcher = CodexSearcher(self.codex, home=h)

    def event(self, tid, item_type, payload):
        self.history.execute("INSERT INTO thread_items VALUES (?,?,?)", (tid, item_type, json.dumps(payload)))

    def search(self, **kwargs):
        return self.searcher.search(SearchQuery(**kwargs))[0]

    def test_repo_matches_sessions_even_if_started_elsewhere(self):
        hits = self.search(repo="dotfiles")
        self.assertEqual({"session-A", "session-B"}, {v["session_id"] for v in hits})
        multi = next(v for v in hits if v["session_id"] == "session-A")
        self.assertEqual("file-activity", multi["evidence_strength"])
        self.assertTrue(any(v["source"] == "fileChange.path" for v in multi["evidence"]))

    def test_remote_url_search_includes_file_activity_from_home_started_session(self):
        hits = self.search(repo="https://github.com/ArthurZakirov/dotfiles")
        self.assertEqual({"session-A", "session-B"}, {v["session_id"] for v in hits})

    def test_cross_repo_many_to_many(self):
        hits_a = self.search(repo="dotfiles")
        hits_b = self.search(repo="AgentDesk")
        self.assertIn("session-A", [h["session_id"] for h in hits_a])
        self.assertIn("session-A", [h["session_id"] for h in hits_b])
        self.assertIn("session-E", [h["session_id"] for h in hits_b])

    def test_equal_strength_matches_show_newest_first(self):
        with sqlite3.connect(self.codex / "state_5.sqlite") as state:
            state.executemany("INSERT INTO threads VALUES (?,?,?,?,?,?,?,?,?)", [
                ("older", "Old AgentDesk", self.repo_b, None, None, None, 700, None, None),
                ("newer", "New AgentDesk", self.repo_b, None, None, None, 900, None, None),
            ])
        ids = [hit["session_id"] for hit in self.search(repo="AgentDesk")]
        self.assertLess(ids.index("newer"), ids.index("older"))

    def test_worktree_matches_paths_even_when_cwd_is_home(self):
        hits = self.search(worktree=self.repo_a_worktree)
        self.assertEqual(["session-A"], [h["session_id"] for h in hits])
        self.assertIn("path inside worktree", hits[0]["evidence"][0]["kind"])

    def test_pr_direct_attachment_not_inferred_from_repo(self):
        hits = self.search(pr="github.com/arthurzakirov/dotfiles/pull/2")
        self.assertEqual(["session-C"], [h["session_id"] for h in hits])
        self.assertEqual("direct", hits[0]["evidence_strength"])
        self.assertEqual(["session-F"], hits[0]["related_child_session_ids"])

    def test_branch_and_repo_and_semantics(self):
        hits = self.search(repo="dotfiles", branch="feat/cross-repo")
        self.assertEqual(["session-B"], [h["session_id"] for h in hits])

    def test_commit_sha_prefix(self):
        hits = self.search(commit="abcdef1")
        self.assertEqual(["session-B"], [h["session_id"] for h in hits])

    def test_jira_from_history_and_title(self):
        hits = self.search(jira="DCP-9712")
        self.assertEqual({"session-A", "session-D"}, {h["session_id"] for h in hits})

    def test_worktree_query_does_not_infer_current_branch(self):
        hits = self.search(worktree=self.repo_a_worktree)
        self.assertEqual(["session-A"], [h["session_id"] for h in hits])

    def test_missing_history_is_a_warning_not_a_crash(self):
        (self.codex / "thread_history_1.sqlite").unlink()
        hits, stats = self.searcher.search(SearchQuery(repo="dotfiles"))
        self.assertEqual(["session-B"], [h["session_id"] for h in hits])
        self.assertFalse(stats["history_available"])
        self.assertTrue(stats["warnings"])

    def test_no_databases_were_modified(self):
        before = (self.codex / "state_5.sqlite").read_bytes()
        self.search(repo="dotfiles")
        after = (self.codex / "state_5.sqlite").read_bytes()
        self.assertEqual(before, after)

    def test_real_cli_json_contract(self):
        # Exercise the installed command's entry point, not only its helpers.
        run = subprocess.run(
            [sys.executable, str(SCRIPT), "--codex-home", str(self.codex),
             "--repo", "dotfiles", "--json"],
            capture_output=True, text=True, check=True,
            env={**os.environ, "HOME": str(self.home)},
        )
        payload = json.loads(run.stdout)
        self.assertEqual({"session-A", "session-B"},
                         {hit["session_id"] for hit in payload["results"]})
        self.assertTrue(payload["stats"]["history_available"])

    def test_malformed_pr_link_in_history_is_ignored(self):
        with sqlite3.connect(self.codex / "thread_history_1.sqlite") as history:
            history.execute("INSERT INTO thread_items VALUES (?,?,?)", (
                "session-A", "userMessage",
                json.dumps({"content": [{"text": "Unrelated https://[bad/pr URL"}]}),
            ))
        hits = self.search(pr="github.com/arthurzakirov/dotfiles/pull/2")
        self.assertEqual(["session-C"], [hit["session_id"] for hit in hits])

    def test_branch_text_does_not_match_longer_branch(self):
        with sqlite3.connect(self.codex / "state_5.sqlite") as db:
            db.execute("UPDATE threads SET title='work feat/foo-old feat/foobar prefixfeat/foo' WHERE id='session-A'")

        hits = self.search(branch="feat/foo")

        self.assertEqual([], hits)

    def test_commit_text_matches_prefix_but_not_middle_of_sha(self):
        with sqlite3.connect(self.codex / "state_5.sqlite") as db:
            db.execute("UPDATE threads SET title='commit 1234567abcdef0' WHERE id='session-A'")

        prefix = self.search(commit="1234567")
        middle = self.search(commit="34567ab")

        self.assertEqual(['session-A'], [h['session_id'] for h in prefix])
        self.assertEqual([], middle)

    def test_reserved_characters_in_codex_directory(self):
        renamed = self.home / 'codex?# space'
        self.codex.rename(renamed)

        hits, _ = CodexSearcher(renamed, home=str(self.home)).search(SearchQuery(repo='dotfiles'))

        self.assertEqual({'session-A', 'session-B'}, {h['session_id'] for h in hits})

    def test_wal_snapshot_reads_committed_rows_without_creating_source_shm(self):
        import shutil
        source = self.home / 'archive'
        source.mkdir()
        writer = sqlite3.connect(self.codex / 'state_5.sqlite')
        self.addCleanup(writer.close)
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute("UPDATE threads SET title='WAL-only title' WHERE id='session-A'")
        writer.commit()
        for suffix in ['', '-wal']:
            shutil.copyfile(str(self.codex / 'state_5.sqlite') + suffix,
                            str(source / 'state_5.sqlite') + suffix)
        before = {p.name: p.read_bytes() for p in source.iterdir()}

        hits, _ = CodexSearcher(source, home=str(self.home)).search(SearchQuery(branch='WAL-only title'))

        self.assertEqual(['session-A'], [h['session_id'] for h in hits])
        self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir()})


class NormalizationTests(unittest.TestCase):
    def test_git_ssh_and_https_share_one_identity(self):
        self.assertEqual(canonical_remote("git@github.com:ArthurZakirov/dotfiles.git"), canonical_remote("https://github.com/ArthurZakirov/dotfiles"))

    def test_bitbucket_pr(self):
        self.assertEqual("bitbucket.org/team/repo/pull-requests/8", canonical_pr("https://bitbucket.org/team/repo/pull-requests/8/diff#one"))

    def test_invalid_pr(self):
        self.assertIsNone(canonical_pr("https://github.com/owner/repo/issues/42"))
        self.assertIsNone(canonical_pr("https://[broken"))
        self.assertIsNone(canonical_remote("https://[broken"))

    def test_invalid_sha(self):
        values = {"repo": None, "branch": None, "worktree": None, "commit": "xyz", "pr": None, "jira": None}
        with self.assertRaises(ValueError):
            SearchQuery.from_args(argparse.Namespace(**values))


class ChatGPTDesktopTests(unittest.TestCase):
    def test_pr_maps_to_transparent_chatgpt_search_term(self):
        self.assertEqual(
            "pull/67",
            module.chatgpt_search_term(SearchQuery(
                pr="github.com/arthurzakirov/dotfiles/pull/67",
            )),
        )
        self.assertEqual("DCP-9712", module.chatgpt_search_term(SearchQuery(jira="DCP-9712")))

    def test_accessibility_results_never_invent_chat_links_or_session_ids(self):
        elements = [
            {"ax_role": "AXStaticText", "value": "Chats besser finden ChatGPT ⌃1"},
            {"ax_role": "AXStaticText", "value": "Chats besser finden"},
            {"ax_role": "AXStaticText", "value": "Some cloud messages may be missing from search"},
            {"ax_role": "AXStaticText", "value": "Rename worktrees properly ChatGPT ⌃2"},
        ]

        hits, warnings = module.parse_chatgpt_suggestions(elements, limit=2)

        self.assertEqual(["Chats besser finden", "Rename worktrees properly"],
                         [x["title"] for x in hits])
        self.assertEqual([1, 2], [x["position"] for x in hits])
        self.assertTrue(all(x["chat_url"] is None and x["session_id"] is None for x in hits))
        self.assertEqual(1, len(warnings))

    def test_chatgpt_provider_operates_via_accessibility_without_network_adapter(self):
        initial = {"snapshot_id": "initial", "ui_elements": []}
        overlay = {"snapshot_id": "overlay", "ui_elements": [
            {"ax_role": "AXComboBox", "label": "Command menu", "id": "input", "value": ""},
        ]}
        result_view = {"snapshot_id": "result", "ui_elements": [
            {"ax_role": "AXComboBox", "label": "Command menu", "id": "input", "value": "pull/67"},
            {"ax_role": "AXStaticText", "value": "Chats besser finden ChatGPT ⌃1"},
        ]}
        responses = [
            {"windows": [{"window_id": 127, "observation_capability": "combined_eligible",
                          "is_on_screen": True}]},
            initial,
            {},
            overlay,
            {},
            result_view,
        ]
        with patch.object(module.ChatGPTDesktopSearcher, "_peekaboo",
                          side_effect=responses) as fake, patch.object(module.time, "sleep"):
            matches, summary = module.ChatGPTDesktopSearcher().search("pull/67")
        self.assertEqual(["Chats besser finden"], [m["title"] for m in matches])
        self.assertFalse(summary["complete_history"])
        self.assertEqual(("press", "cmd+k", "--window-id", "127", "--foreground"),
                         fake.call_args_list[2].args)
        self.assertEqual("set-value", fake.call_args_list[4].args[0])

    def test_chatgpt_only_cli_requires_no_codex_database(self):
        sample = [{"provider": "chatgpt", "title": "Chats besser finden",
                   "position": 1, "session_id": None, "chat_url": None}]
        summary = {"query": "pull/67", "count": 1, "complete_history": False, "warnings": []}
        with patch.object(module.ChatGPTDesktopSearcher, "search",
                          return_value=(sample, summary)), patch("sys.stdout", new_callable=io.StringIO) as out:
            exit_code = main(["--chatgpt-query", "pull/67", "--json"])
        self.assertEqual(0, exit_code)
        payload = json.loads(out.getvalue())
        self.assertEqual(0, payload["stats"]["total_matches"])
        self.assertTrue(payload["stats"]["native_codex_search_skipped"])
        self.assertEqual("Chats besser finden", payload["chatgpt_results"][0]["title"])

    def test_chatgpt_unavailable_returns_error_not_false_zero_results(self):
        with patch.object(module.ChatGPTDesktopSearcher, "search",
                          side_effect=RuntimeError("No accessible ChatGPT window")), \
                patch("sys.stderr", new_callable=io.StringIO) as err:
            exit_code = main(["--chatgpt-query", "pull/67"])
        self.assertEqual(2, exit_code)
        self.assertIn("No accessible ChatGPT window", err.getvalue())



if __name__ == "__main__":
    unittest.main()
