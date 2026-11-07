"""Offline contract tests for the read-only session search core."""
import argparse
import json
import os
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
session_find = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = session_find
loader.exec_module(session_find)
CodexSearcher = session_find.CodexSearcher
SearchQuery = session_find.SearchQuery
canonical_pr = session_find.canonical_pr
canonical_remote = session_find.canonical_remote
main = session_find.main


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


class NormalizationTests(unittest.TestCase):
    def test_git_ssh_and_https_share_one_identity(self):
        self.assertEqual(canonical_remote("git@github.com:ArthurZakirov/dotfiles.git"), canonical_remote("https://github.com/ArthurZakirov/dotfiles"))

    def test_bitbucket_pr(self):
        self.assertEqual("bitbucket.org/team/repo/pull-requests/8", canonical_pr("https://bitbucket.org/team/repo/pull-requests/8/diff#one"))

    def test_invalid_pr(self):
        self.assertIsNone(canonical_pr("https://github.com/owner/repo/issues/42"))

    def test_malformed_ipv6_url_in_history_is_ignored(self):
        self.assertIsNone(canonical_pr("https://[redacted]/owner/repo/pull/42"))
        self.assertIsNone(canonical_remote("https://[redacted]/owner/repo"))

    def test_symlinked_parent_path_resolves_repo_name(self):
        with tempfile.TemporaryDirectory() as temp:
            real_home = Path(temp) / "real-home"
            real_home.mkdir()
            alias = Path(temp) / "alias"
            alias.symlink_to(real_home, target_is_directory=True)
            historical_path = alias / "Repos/dotfiles.worktrees/feature/src/x.py"
            self.assertEqual("dotfiles", session_find.repo_name_from_path(str(historical_path), str(real_home)))

    def test_invalid_sha(self):
        values = {"repo": None, "branch": None, "worktree": None, "commit": "xyz", "pr": None, "jira": None}
        with self.assertRaises(ValueError):
            SearchQuery.from_args(argparse.Namespace(**values))


if __name__ == "__main__":
    unittest.main()