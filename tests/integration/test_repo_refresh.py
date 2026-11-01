"""CLI-to-filesystem tests using real Git and disposable local remotes only."""

from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "home/dot_local/bin/executable_repo-refresh"


def git(repo, *args, check=True):
    result = subprocess.run(["git", "-C", str(repo), *map(str, args)],
                            capture_output=True, text=True, timeout=30)
    if check:
        assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@dataclass
class Scenario:
    repo: Path
    upstream: Path
    remote: Path
    config: Path
    state: Path
    worktrees: Path

    @property
    def command(self):
        return [sys.executable, str(CLI), "--config", str(self.config),
                "--state-dir", str(self.state)]

    def outcome(self):
        return json.loads((self.state / "status.json").read_text())["repositories"][0]

    def advance(self):
        (self.upstream / "upstream.txt").write_text("new upstream content\n")
        git(self.upstream, "add", ".")
        git(self.upstream, "commit", "-m", "Upstream change")
        git(self.upstream, "push", "origin", "HEAD")


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    # No developer credentials, hooks, identity, Git config or repository routing.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(key, raising=False)
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.invalid")
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-b", "main")
    (upstream / "tracked.txt").write_text("original\n")
    (upstream / ".gitignore").write_text("ignored/\n")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "Initial")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", str(upstream), str(remote)],
                   check=True, capture_output=True)
    git(upstream, "remote", "add", "origin", remote)
    root = tmp_path / "Repos"
    repo = root / "project"
    repo.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(remote), str(repo)], check=True, capture_output=True)
    config = tmp_path / "config.json"
    worktrees = root / "project.worktrees"
    config.write_text(json.dumps({"root": str(root)}))
    return Scenario(repo, upstream, remote, config, tmp_path / "state", worktrees)


@pytest.mark.parametrize("integration", ["merge", "squash"])
@pytest.mark.parametrize("default", ["main", "master"])
def test_merged_branch_is_cleaned_locally_and_on_remote(scenario, integration, default):
    if default == "master":
        git(scenario.upstream, "branch", "master", "main")
        git(scenario.upstream, "switch", "master")
        git(scenario.upstream, "push", "origin", "master")
        git(scenario.remote, "symbolic-ref", "HEAD", "refs/heads/master")
        git(scenario.repo, "fetch", "origin", "master")
        git(scenario.repo, "switch", "-c", "master", "origin/master")
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "feature.txt").write_text("shipped\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Implement feature")
    (scenario.repo / "detail.txt").write_text("more work\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Complete feature")
    git(scenario.repo, "push", "-u", "origin", "feature")
    git(scenario.repo, "switch", default)
    scenario.worktrees.mkdir()
    worktree = scenario.worktrees / "feature"
    git(scenario.repo, "worktree", "add", worktree, "feature")

    git(scenario.upstream, "fetch", "origin", "feature")
    if integration == "squash":
        git(scenario.upstream, "merge", "--squash", "origin/feature")
        git(scenario.upstream, "commit", "-m", "Squash delivery with a different message")
    else:
        git(scenario.upstream, "merge", "--no-ff", "-m", "Merge delivered feature",
            "origin/feature")
    git(scenario.upstream, "push", "origin", default)

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    cleaned = scenario.outcome()["branches"][0]
    assert cleaned["state"] == "merged-cleaned"
    assert cleaned["proof"].startswith("squash:" if integration == "squash" else "ancestor")
    assert cleaned["remote"] == "deleted"
    assert not worktree.exists()
    assert git(scenario.repo, "show-ref", "--verify", "refs/heads/feature",
               check=False) == ""
    assert git(scenario.remote, "show-ref", "--verify", "refs/heads/feature",
               check=False) == ""


@pytest.mark.parametrize("local_data", ["tracked", "untracked", "ignored"])
def test_merged_branch_preserves_worktree_with_local_data(scenario, local_data):
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "feature.txt").write_text("shipped\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Feature")
    git(scenario.repo, "push", "origin", "feature")
    git(scenario.repo, "switch", "main")
    scenario.worktrees.mkdir()
    worktree = scenario.worktrees / "feature"
    git(scenario.repo, "worktree", "add", worktree, "feature")
    if local_data == "tracked":
        (worktree / "feature.txt").write_text("uncommitted edit\n")
    elif local_data == "untracked":
        (worktree / "notes.txt").write_text("unique local notes\n")
    else:
        (worktree / "ignored").mkdir()
        (worktree / "ignored/secret.txt").write_text("unique ignored data\n")
    git(scenario.upstream, "fetch", "origin", "feature")
    git(scenario.upstream, "merge", "--squash", "origin/feature")
    git(scenario.upstream, "commit", "-m", "Squashed implementation")
    git(scenario.upstream, "push", "origin", "main")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    branch = scenario.outcome()["branches"][0]
    assert branch["state"] == "merged-protected"
    assert "Uncommitted" in branch["reason"]
    assert worktree.exists()
    assert git(scenario.repo, "rev-parse", "refs/heads/feature")
    assert git(scenario.remote, "rev-parse", "refs/heads/feature")


def test_clean_merged_branch_removes_only_confirmed_build_caches(scenario):
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "feature.txt").write_text("shipped\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Feature")
    git(scenario.repo, "push", "origin", "feature")
    git(scenario.repo, "switch", "main")
    scenario.worktrees.mkdir()
    worktree = scenario.worktrees / "feature"
    git(scenario.repo, "worktree", "add", worktree, "feature")
    with (worktree / ".gitignore").open("a") as ignore:
        ignore.write("/node_modules/\n/.next/\n/out/\n")
    for name in ("node_modules", ".next", "out"):
        folder = worktree / name
        folder.mkdir()
        (folder / "cache").write_text("generated\n")
    # The .gitignore is tracked and would block cleanup, so commit it on branch.
    git(worktree, "add", ".gitignore")
    git(worktree, "commit", "-m", "Ignore build output")
    git(worktree, "push", "origin", "feature")
    git(scenario.upstream, "fetch", "origin", "feature")
    git(scenario.upstream, "merge", "--squash", "origin/feature")
    git(scenario.upstream, "commit", "-m", "Publish website")
    git(scenario.upstream, "push", "origin", "main")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert scenario.outcome()["branches"][0]["state"] == "merged-cleaned"
    assert not worktree.exists()


def test_partial_squash_does_not_trigger_branch_deletion(scenario):
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "one.txt").write_text("one\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Part one")
    first = git(scenario.repo, "rev-parse", "HEAD")
    (scenario.repo / "two.txt").write_text("two\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Part two")
    git(scenario.repo, "push", "origin", "feature")
    git(scenario.repo, "switch", "main")
    git(scenario.upstream, "fetch", "origin", "feature")
    git(scenario.upstream, "cherry-pick", first)
    git(scenario.upstream, "push", "origin", "main")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode in (0, 1)
    assert scenario.outcome()["branches"][0]["state"] != "merged-cleaned"
    assert git(scenario.repo, "rev-parse", "refs/heads/feature")
    assert git(scenario.remote, "rev-parse", "refs/heads/feature")


def test_squash_with_matching_commit_message_is_not_enough(scenario):
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "feature.txt").write_text("unfinished content\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Same summary")
    git(scenario.repo, "push", "origin", "feature")
    git(scenario.repo, "switch", "main")
    (scenario.upstream / "different.txt").write_text("different content\n")
    git(scenario.upstream, "add", ".")
    git(scenario.upstream, "commit", "-m", "Same summary")
    git(scenario.upstream, "push", "origin", "main")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode in (0, 1)
    assert scenario.outcome()["branches"][0]["state"] != "merged-cleaned"
    assert git(scenario.repo, "rev-parse", "refs/heads/feature")
    assert git(scenario.remote, "rev-parse", "refs/heads/feature")


def test_remote_branch_with_additional_commits_is_preserved(scenario):
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "feature.txt").write_text("shipped\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Feature")
    original = git(scenario.repo, "rev-parse", "HEAD")
    git(scenario.repo, "push", "origin", "feature")
    git(scenario.repo, "switch", "main")
    git(scenario.upstream, "fetch", "origin", "feature")
    git(scenario.upstream, "merge", "--squash", "origin/feature")
    git(scenario.upstream, "commit", "-m", "Squashed feature")
    git(scenario.upstream, "push", "origin", "main")
    git(scenario.upstream, "switch", "-c", "feature", "origin/feature")
    (scenario.upstream / "extra.txt").write_text("new remote work\n")
    git(scenario.upstream, "add", ".")
    git(scenario.upstream, "commit", "-m", "Extra unmerged work")
    newer = git(scenario.upstream, "rev-parse", "HEAD")
    git(scenario.upstream, "push", "origin", "feature")
    git(scenario.upstream, "switch", "main")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert scenario.outcome()["branches"][0]["state"] == "merged-cleaned"
    assert scenario.outcome()["branches"][0]["remote"] == "different-tip-preserved"
    assert git(scenario.remote, "rev-parse", "refs/heads/feature") == newer
    assert newer != original


def test_only_direct_clone_directories_are_refreshed(scenario, tmp_path):
    nested = scenario.repo.parent / "tmp" / "experiment"
    nested.parent.mkdir()
    subprocess.run(["git", "clone", str(scenario.remote), str(nested)],
                   check=True, capture_output=True)
    git(nested, "switch", "-c", "unfinished")
    (nested / "untracked.txt").write_text("keep me\n")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (scenario.repo / "upstream.txt").is_file()
    assert git(nested, "branch", "--show-current") == "unfinished"
    assert (nested / "untracked.txt").read_text() == "keep me\n"
    assert len(json.loads((scenario.state / "status.json").read_text())["repositories"]) == 1


@pytest.mark.parametrize("branch", ["main", "master", "trunk"])
def test_clean_checkout_tracks_actual_remote_default(scenario, branch):
    if branch != "main":
        git(scenario.remote, "branch", branch, "main")
        git(scenario.remote, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    else:
        scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert git(scenario.repo, "branch", "--show-current") == branch
    assert git(scenario.repo, "rev-parse", "HEAD") == git(scenario.remote, "rev-parse", branch)
    assert git(scenario.repo, "status", "--porcelain") == ""
    assert git(scenario.repo, "rev-parse", "--abbrev-ref", "@{upstream}") == f"origin/{branch}"
    assert git(scenario.repo, "symbolic-ref", "refs/remotes/origin/HEAD") == f"refs/remotes/origin/{branch}"


@pytest.mark.parametrize("branch", ["main", "feature/unfinished", None])
def test_forces_default_and_preserves_complete_working_state(scenario, branch):
    if branch is None:
        git(scenario.repo, "checkout", "--detach")
    elif branch != "main":
        git(scenario.repo, "switch", "-c", branch)
    (scenario.repo / "tracked.txt").write_text("staged\n")
    git(scenario.repo, "add", "tracked.txt")
    (scenario.repo / "tracked.txt").write_text("unstaged\n")
    (scenario.repo / "untracked.txt").write_text("untracked\n")
    (scenario.repo / "ignored").mkdir()
    (scenario.repo / "ignored/local.txt").write_text("ignored\n")
    (scenario.repo / "link").symlink_to("tracked.txt")
    executable = scenario.repo / "executable"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    outcome = scenario.outcome()
    recovery = Path(outcome["recovery"])
    assert git(scenario.repo, "branch", "--show-current") == "main"
    assert git(scenario.repo, "status", "--porcelain") == ""
    assert (recovery / "tracked.txt").read_text() == "unstaged\n"
    assert git(recovery, "show", ":tracked.txt") == "staged"
    assert (recovery / "untracked.txt").read_text() == "untracked\n"
    assert (recovery / "ignored/local.txt").read_text() == "ignored\n"
    assert os.readlink(recovery / "link") == "tracked.txt"
    assert os.access(recovery / "executable", os.X_OK)
    assert recovery.stat().st_mode & 0o077 == 0
    development = Path(outcome.get("development_worktree", str(recovery)))
    assert git(development, "branch", "--show-current") == (branch if branch and branch != "main" else "")


@pytest.mark.parametrize("force_push", [False, True])
def test_preserves_local_default_commits_before_forced_replacement(scenario, force_push):
    (scenario.repo / "local.txt").write_text("unpublished\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Local only")
    old = git(scenario.repo, "rev-parse", "HEAD")
    scenario.advance()
    if force_push:
        git(scenario.upstream, "checkout", "--orphan", "replacement")
        git(scenario.upstream, "commit", "-m", "Rewritten history")
        git(scenario.upstream, "push", "--force", "origin", "HEAD:main")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    recovery = Path(scenario.outcome()["recovery"])
    assert git(recovery, "rev-parse", "HEAD") == old
    assert (recovery / "local.txt").read_text() == "unpublished\n"
    assert git(scenario.repo, "rev-parse", "HEAD") == git(scenario.remote, "rev-parse", "main")
    assert old in git(scenario.repo, "for-each-ref", "--format=%(objectname)", "refs/repo-refresh/")


@pytest.mark.parametrize("operation", ["merge", "rebase"])
def test_preserves_conflicted_index_and_quits_interrupted_operation(scenario, operation):
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "tracked.txt").write_text("feature\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Feature")
    git(scenario.repo, "switch", "main")
    (scenario.repo / "tracked.txt").write_text("main\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Main")
    git(scenario.repo, "switch", "feature")
    git(scenario.repo, operation, "main", check=False)
    conflicts = git(scenario.repo, "ls-files", "--unmerged")
    assert conflicts
    contents = (scenario.repo / "tracked.txt").read_text()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    recovery = Path(scenario.outcome()["recovery"])
    assert (recovery / "tracked.txt").read_text() == contents
    assert git(recovery, "ls-files", "--unmerged") == conflicts
    assert git(scenario.repo, "branch", "--show-current") == "main"
    assert git(scenario.repo, "status", "--porcelain") == ""
    assert "rebase in progress" not in git(scenario.repo, "status")


def test_releases_default_branch_in_another_worktree_without_changing_its_files(scenario, tmp_path):
    git(scenario.repo, "switch", "-c", "feature")
    other = tmp_path / "existing-main"
    git(scenario.repo, "worktree", "add", other, "main")
    old = git(other, "rev-parse", "HEAD")
    (other / "tracked.txt").write_text("other worktree changes\n")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert git(scenario.repo, "branch", "--show-current") == "main"
    assert git(other, "branch", "--show-current") == ""
    assert git(other, "rev-parse", "HEAD") == old
    assert (other / "tracked.txt").read_text() == "other worktree changes\n"


def test_offline_repo_is_untouched_and_does_not_block_other_repos(scenario):
    broken = scenario.repo.parent / "broken"
    subprocess.run(["git", "clone", str(scenario.remote), str(broken)], check=True, capture_output=True)
    git(broken, "remote", "set-url", "origin", "/nonexistent-test-remote")
    git(broken, "switch", "-c", "keep-me")
    (broken / "tracked.txt").write_text("unsaved\n")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 1
    assert (broken / "tracked.txt").read_text() == "unsaved\n"
    assert git(broken, "branch", "--show-current") == "keep-me"
    assert (scenario.repo / "upstream.txt").is_file()


def test_repeated_run_does_not_create_more_recovery_worktrees(scenario):
    git(scenario.repo, "switch", "-c", "feature")
    first = subprocess.run(scenario.command, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    worktrees = git(scenario.repo, "worktree", "list", "--porcelain")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0
    assert scenario.outcome()["state"] == "current"
    assert git(scenario.repo, "worktree", "list", "--porcelain") == worktrees


def test_development_and_recovery_worktree_names_identify_the_branch(scenario):
    git(scenario.repo, "switch", "-c", "feat/clear-branch-purpose")
    (scenario.repo / "feature.txt").write_text("keep this work\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Feature")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    outcome = scenario.outcome()
    development = Path(outcome["development_worktree"])
    recovery = Path(outcome["recovery"])
    assert development.parent == scenario.repo.with_name("project.worktrees")
    assert recovery.parent == development.parent
    assert development.name == "feat-clear-branch-purpose"
    assert re.fullmatch(
        r"recovery-feat-clear-branch-purpose-\d{4}-\d{2}-\d{2}--\d{2}-\d{2}-\d{2}-[0-9a-f]{12}",
        recovery.name,
    )
    assert git(development, "branch", "--show-current") == "feat/clear-branch-purpose"
    assert (development / "feature.txt").read_text() == "keep this work\n"
    assert (recovery / "feature.txt").read_text() == "keep this work\n"


@pytest.mark.parametrize(
    ("branch", "expected_slug"),
    [("+++", "branch-u2b-u2b-u2b"), ("🚀", "branch-u1f680")],
)
def test_symbol_only_branch_names_remain_identifiable(scenario, branch, expected_slug):
    git(scenario.repo, "switch", "-c", branch)
    (scenario.repo / "feature.txt").write_text("symbol-only branch work\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Feature")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    outcome = scenario.outcome()
    development = Path(outcome["development_worktree"])
    recovery = Path(outcome["recovery"])
    assert development.name == expected_slug
    assert recovery.name.startswith(f"recovery-{expected_slug}-")
    assert git(development, "branch", "--show-current") == branch
    assert (recovery / "feature.txt").read_text() == "symbol-only branch work\n"


def test_default_branch_recovery_name_identifies_its_source(scenario):
    (scenario.repo / "tracked.txt").write_text("local edits\n")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    recovery = Path(scenario.outcome()["recovery"])
    assert re.fullmatch(
        r"recovery-main-\d{4}-\d{2}-\d{2}--\d{2}-\d{2}-\d{2}-[0-9a-f]{12}",
        recovery.name,
    )
    assert (recovery / "tracked.txt").read_text() == "local edits\n"


def test_equivalent_slugs_get_distinct_worktree_paths(scenario):
    git(scenario.repo, "branch", "feat/foo-bar")
    git(scenario.repo, "branch", "feat-foo/bar")
    for branch in ("feat/foo-bar", "feat-foo/bar"):
        git(scenario.repo, "switch", branch)
        (scenario.repo / f"{branch.replace('/', '-')}.txt").write_text(branch + "\n")
        git(scenario.repo, "add", ".")
        git(scenario.repo, "commit", "-m", f"Distinct work for {branch}")
    git(scenario.repo, "switch", "main")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    outcomes = {entry["branch"]: entry for entry in scenario.outcome()["branches"]}
    names = {branch: Path(entry["worktree"]).name for branch, entry in outcomes.items()}
    assert len(set(names.values())) == 2
    assert all(name.startswith("feat-foo-bar") for name in names.values())
    for branch, entry in outcomes.items():
        assert git(Path(entry["worktree"]), "branch", "--show-current") == branch


@pytest.mark.parametrize("checked_out", [False, True])
def test_rebases_every_local_feature_branch_and_protects_original_commits(scenario, tmp_path, checked_out):
    git(scenario.repo, "config", "rebase.updateRefs", "true")
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "feature.txt").write_text("feature work\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Feature commit")
    original = git(scenario.repo, "rev-parse", "HEAD")
    git(scenario.repo, "switch", "main")
    existing = tmp_path / "feature-worktree"
    if checked_out:
        git(scenario.repo, "worktree", "add", existing, "feature")
    git(scenario.repo, "branch", "another-feature", original)
    scenario.advance()
    target = git(scenario.remote, "rev-parse", "main")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    outcomes = {item["branch"]: item for item in scenario.outcome()["branches"]}
    assert set(outcomes) == {"feature", "another-feature"}
    for branch, outcome in outcomes.items():
        assert outcome["state"] == "rebased"
        assert git(scenario.repo, "merge-base", target, branch) == target
        assert git(scenario.repo, "rev-parse", branch) != original
        worktree = Path(outcome["worktree"])
        assert (worktree / "feature.txt").read_text() == "feature work\n"
        assert git(worktree, "branch", "--show-current") == branch
        assert git(Path(outcome["recovery"]), "rev-parse", "HEAD") == original
    if checked_out:
        assert Path(outcomes["feature"]["worktree"]) == existing
    # The updater rewrites local branches only, never publishing them.
    assert not git(scenario.remote, "for-each-ref", "--format=%(refname)", "refs/heads/feature")


def test_failed_rebase_is_not_retried_every_minute(scenario):
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "feature.txt").write_text("feature work\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Feature")
    git(scenario.repo, "switch", "main")
    linked = scenario.worktrees / "feature"
    scenario.worktrees.mkdir()
    git(scenario.repo, "worktree", "add", linked, "feature")
    marker = Path(git(linked, "rev-parse", "--path-format=absolute",
                      "--git-path", "repo-refresh-rebase.json"))
    previous = {"branch": "feature", "state": "failed",
                "worktree": str(linked), "base": git(scenario.repo, "rev-parse", "HEAD")}
    marker.write_text(json.dumps(previous))
    scenario.advance()

    first = subprocess.run(scenario.command, capture_output=True, text=True)
    saved_worktrees = git(scenario.repo, "worktree", "list", "--porcelain")
    repeated = subprocess.run(scenario.command, capture_output=True, text=True)

    assert first.returncode == 1, first.stdout + first.stderr
    assert repeated.returncode == 1, repeated.stdout + repeated.stderr
    assert scenario.outcome()["branches"][0] == previous
    assert git(scenario.repo, "worktree", "list", "--porcelain") == saved_worktrees
    assert marker.read_text() == json.dumps(previous)


def test_generated_ignored_caches_are_not_copied_into_recovery(scenario):
    git(scenario.repo, "switch", "-c", "feature")
    with (scenario.repo / ".gitignore").open("a") as stream:
        stream.write("/node_modules/\n/.next/\n/out/\n")
    for folder in ("node_modules", ".next", "out"):
        cache = scenario.repo / folder
        cache.mkdir()
        (cache / "generated.tmp").write_text("rebuildable\n")
    (scenario.repo / "ignored").mkdir()
    (scenario.repo / "ignored/valuable-local.txt").write_text("preserve me\n")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    recovery = Path(scenario.outcome()["recovery"])
    assert (recovery / "ignored/valuable-local.txt").read_text() == "preserve me\n"
    assert all(not (recovery / name).exists()
               for name in ("node_modules", ".next", "out"))
    assert (scenario.repo.with_name("project.worktrees") / "feature").exists()


def test_rebase_conflicts_remain_visible_and_are_not_restarted_on_the_next_tick(scenario, tmp_path):
    git(scenario.repo, "switch", "-c", "healthy")
    (scenario.repo / "healthy.txt").write_text("independent unmerged work\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Healthy branch work")
    git(scenario.repo, "switch", "main")
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "tracked.txt").write_text("feature change\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Feature")
    original = git(scenario.repo, "rev-parse", "HEAD")
    git(scenario.repo, "switch", "main")
    (scenario.upstream / "tracked.txt").write_text("upstream conflict\n")
    git(scenario.upstream, "add", ".")
    git(scenario.upstream, "commit", "-m", "Conflicting upstream")
    git(scenario.upstream, "push", "origin", "HEAD")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    branch = scenario.outcome()["branches"][0]
    assert branch["state"] == "conflicts"
    assert scenario.outcome()["branches"][1]["state"] == "rebased"
    worktree = Path(branch["worktree"])
    assert git(worktree, "ls-files", "--unmerged")
    assert "<<<<<<<" in (worktree / "tracked.txt").read_text()
    assert git(Path(branch["recovery"]), "rev-parse", "HEAD") == original
    before = git(scenario.repo, "worktree", "list", "--porcelain")
    contents = (worktree / "tracked.txt").read_text()

    repeated = subprocess.run(scenario.command, capture_output=True, text=True)

    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    assert scenario.outcome()["branches"][0]["state"] == "conflicts"
    assert git(scenario.repo, "worktree", "list", "--porcelain") == before
    assert (worktree / "tracked.txt").read_text() == contents
    # Human resolution is respected; the next scheduled run sees a current branch.
    (worktree / "tracked.txt").write_text("resolved\n")
    git(worktree, "add", ".")
    git(worktree, "-c", "core.editor=true", "rebase", "--continue")

    resolved = subprocess.run(scenario.command, capture_output=True, text=True)

    assert resolved.returncode == 0, resolved.stdout + resolved.stderr
    assert scenario.outcome()["branches"][0]["state"] == "current"
    assert git(worktree, "branch", "--show-current") == "feature"


def test_dirty_feature_worktree_keeps_staged_and_unstaged_edits_after_rebase(scenario, tmp_path):
    existing = tmp_path / "feature-worktree"
    git(scenario.repo, "worktree", "add", "-b", "feature", existing)
    (existing / "committed-feature.txt").write_text("unique unmerged commit\n")
    git(existing, "add", ".")
    git(existing, "commit", "-m", "Unmerged feature change")
    (existing / "tracked.txt").write_text("staged\n")
    git(existing, "add", "tracked.txt")
    (existing / "tracked.txt").write_text("unstaged\n")
    (existing / "untracked").write_text("untracked\n")
    (existing / "ignored").mkdir()
    (existing / "ignored/cache").write_text("ignored\n")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    branch = scenario.outcome()["branches"][0]
    assert branch["state"] == "rebased"
    assert git(existing, "show", ":tracked.txt") == "staged"
    assert (existing / "tracked.txt").read_text() == "unstaged\n"
    assert (existing / "untracked").read_text() == "untracked\n"
    recovery = Path(branch["recovery"])
    assert git(recovery, "show", ":tracked.txt") == "staged"
    assert (recovery / "ignored/cache").read_text() == "ignored\n"


def test_excludes_main_master_and_actual_remote_default_from_branch_rebases(scenario):
    git(scenario.repo, "branch", "master")
    original = git(scenario.repo, "rev-parse", "master")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert scenario.outcome()["branches"] == []
    assert git(scenario.repo, "rev-parse", "master") == original


@pytest.mark.parametrize("staged", [False, True])
def test_rebase_edit_restore_conflicts_keep_original_changes_recoverable(scenario, tmp_path, staged):
    existing = tmp_path / "feature-worktree"
    git(scenario.repo, "worktree", "add", "-b", "feature", existing)
    (existing / "committed-feature.txt").write_text("unique unmerged commit\n")
    git(existing, "add", ".")
    git(existing, "commit", "-m", "Unmerged feature change")
    (existing / "tracked.txt").write_text("unfinished local edit\n")
    if staged:
        git(existing, "add", ".")
    (scenario.upstream / "tracked.txt").write_text("upstream change\n")
    git(scenario.upstream, "add", ".")
    git(scenario.upstream, "commit", "-m", "Upstream")
    git(scenario.upstream, "push", "origin", "HEAD")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    branch = scenario.outcome()["branches"][0]
    assert branch["state"] in {"conflicts", "edits-pending"}
    recovery = Path(branch["recovery"])
    assert (recovery / "tracked.txt").read_text() == "unfinished local edit\n"
    if staged:
        assert git(recovery, "show", ":tracked.txt") == "unfinished local edit"
    assert git(existing, "merge-base", "HEAD", "main") == git(scenario.repo, "rev-parse", "main")


def test_preservation_failure_leaves_original_checkout_untouched(scenario):
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "tracked.txt").write_text("important\n")
    os.mkfifo(scenario.repo / "unsupported-pipe")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 1
    assert scenario.outcome()["state"] == "failed"
    assert git(scenario.repo, "branch", "--show-current") == "feature"
    assert (scenario.repo / "tracked.txt").read_text() == "important\n"


def test_redirected_working_tree_is_not_reset_without_its_files_being_preserved(scenario, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "tracked.txt").write_text("must not be reset\n")
    git(scenario.repo, "config", "core.worktree", outside)

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 1
    assert (outside / "tracked.txt").read_text() == "must not be reset\n"
    assert scenario.outcome()["state"] == "failed"


def test_recovery_directory_symlink_cannot_redirect_copy_into_source(scenario):
    git(scenario.repo, "switch", "-c", "feature")
    scenario.worktrees.symlink_to(scenario.repo)

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 1
    assert git(scenario.repo, "branch", "--show-current") == "feature"
    assert not (scenario.repo / "recovery-main").exists()


def test_git_lock_failure_retains_a_usable_recovery(scenario):
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "tracked.txt").write_text("important\n")
    (scenario.repo / ".git/index.lock").touch()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 1
    recoveries = list(scenario.worktrees.rglob("tracked.txt"))
    assert recoveries and recoveries[0].read_text() == "important\n"
    assert (scenario.repo / "tracked.txt").read_text() == "important\n"


@pytest.mark.parametrize("remote_tracks_module", [False, True])
def test_submodule_edits_have_independent_recovery_metadata(scenario, tmp_path, monkeypatch,
                                                          remote_tracks_module):
    module = tmp_path / "module"
    module.mkdir()
    git(module, "init", "-b", "main")
    (module / "file").write_text("module original\n")
    git(module, "add", ".")
    git(module, "commit", "-m", "Module")
    git(scenario.repo, "-c", "protocol.file.allow=always", "submodule", "add", module, "module")
    git(scenario.repo, "commit", "-am", "Local submodule")
    if remote_tracks_module:
        git(scenario.repo, "push", "origin", "HEAD")
        monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    (scenario.repo / "module/file").write_text("module edits\n")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    recovery = Path(scenario.outcome()["recovery"])
    assert (recovery / "module/file").read_text() == "module edits\n"
    assert (recovery / "module/.git").is_dir()
    assert git(recovery / "module", "status", "--porcelain") == "M file"
    assert git(scenario.repo, "status", "--porcelain") == ""


def test_existing_linked_development_worktrees_are_not_repeatedly_reclaimed(scenario):
    linked = scenario.repo.parent / "development"
    git(scenario.repo, "worktree", "add", "-b", "feature", linked)
    (linked / "tracked.txt").write_text("active development\n")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert git(linked, "branch", "--show-current") == "feature"
    assert (linked / "tracked.txt").read_text() == "active development\n"
    outcomes = json.loads((scenario.state / "status.json").read_text())["repositories"]
    assert len(outcomes) == 1


def test_initialized_unborn_checkout_preserves_staged_files(scenario, tmp_path):
    parent = tmp_path / "unborn-parent"
    parent.mkdir()
    root = parent / "project"
    root.mkdir()
    git(root, "init", "-b", "unfinished")
    git(root, "remote", "add", "origin", scenario.remote)
    (root / "local.txt").write_text("first staged file\n")
    git(root, "add", ".")
    config = json.loads(scenario.config.read_text())
    config["root"] = str(parent)
    scenario.config.write_text(json.dumps(config))

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert git(root, "branch", "--show-current") == "main"
    recovery = Path(scenario.outcome()["recovery"])
    assert (recovery / "local.txt").read_text() == "first staged file\n"
    assert git(recovery, "show", ":local.txt") == "first staged file"
    development = Path(scenario.outcome()["development_worktree"])
    assert git(development, "branch", "--show-current") == "unfinished"


def test_sparse_checkout_is_restored_to_a_full_default_checkout(scenario):
    (scenario.upstream / "included").mkdir()
    (scenario.upstream / "excluded").mkdir()
    (scenario.upstream / "included/file").write_text("included\n")
    (scenario.upstream / "excluded/file").write_text("excluded\n")
    git(scenario.upstream, "add", ".")
    git(scenario.upstream, "commit", "-m", "Directories")
    git(scenario.upstream, "push", "origin", "HEAD")
    git(scenario.repo, "pull", "--ff-only")
    git(scenario.repo, "sparse-checkout", "set", "included")
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "included/file").write_text("unfinished\n")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (scenario.repo / "excluded/file").read_text() == "excluded\n"
    recovery = Path(scenario.outcome()["recovery"])
    assert (recovery / "included/file").read_text() == "unfinished\n"


def test_narrow_clone_refspec_does_not_prevent_tracking_remote_default(scenario):
    git(scenario.remote, "branch", "topic", "main")
    git(scenario.repo, "config", "remote.origin.fetch", "+refs/heads/topic:refs/remotes/origin/topic")
    scenario.advance()

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (scenario.repo / "upstream.txt").exists()
    assert git(scenario.repo, "rev-parse", "--abbrev-ref", "@{upstream}") == "origin/main"


def test_split_index_is_recoverable(scenario):
    git(scenario.repo, "update-index", "--split-index")
    (scenario.repo / "tracked.txt").write_text("staged\n")
    git(scenario.repo, "add", "tracked.txt")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    recovery = Path(scenario.outcome()["recovery"])
    assert git(recovery, "show", ":tracked.txt") == "staged"


def test_ignored_collision_is_preserved_before_remote_file_replaces_it(scenario):
    (scenario.repo / "ignored").mkdir()
    (scenario.repo / "ignored/local").write_text("local ignored content\n")
    (scenario.upstream / "ignored").mkdir()
    (scenario.upstream / "ignored/local").write_text("remote tracked content\n")
    git(scenario.upstream, "add", "--force", "ignored/local")
    git(scenario.upstream, "commit", "-m", "Track previously ignored path")
    git(scenario.upstream, "push", "origin", "HEAD")

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (scenario.repo / "ignored/local").read_text() == "remote tracked content\n"
    recovery = Path(scenario.outcome()["recovery"])
    assert (recovery / "ignored/local").read_text() == "local ignored content\n"


@pytest.mark.parametrize("mode", ["disabled", "legacy-worktrees", "locked", "empty-root", "invalid-enabled"])
def test_configuration_and_run_lock_prevent_mutation(scenario, mode):
    git(scenario.repo, "switch", "-c", "feature")
    config = json.loads(scenario.config.read_text())
    handle = None
    if mode == "disabled":
        config["enabled"] = False
    elif mode == "legacy-worktrees":
        config["worktrees"] = str(scenario.worktrees)
    elif mode == "empty-root":
        config["root"] = ""
    elif mode == "invalid-enabled":
        config["enabled"] = "false"
    elif mode == "locked":
        scenario.state.mkdir()
        handle = (scenario.state / "run.lock").open("a")
        fcntl.flock(handle, fcntl.LOCK_EX)
    scenario.config.write_text(json.dumps(config))
    try:
        result = subprocess.run(scenario.command, capture_output=True, text=True)
    finally:
        if handle:
            handle.close()

    assert result.returncode == (1 if mode in ("legacy-worktrees", "empty-root", "invalid-enabled") else 0)
    assert git(scenario.repo, "branch", "--show-current") == "feature"
    assert not scenario.worktrees.exists()


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_chezmoi_installs_executable_schedule_and_reconciles_configuration(
        scenario, profile_factory, profile):
    rendered = profile_factory.render(profile)
    home = Path.home()  # scenario fixture supplies a disposable HOME
    command = ["chezmoi", "--source", str(ROOT), "--config", str(rendered.config),
               "--destination", str(home), "apply", "--exclude", "scripts", "--force"]

    subprocess.run(command, check=True, capture_output=True)

    executable = home / ".local/bin/repo-refresh"
    assert os.access(executable, os.X_OK)
    config = home / ".config/repo-refresh/config.json"
    assert json.loads(config.read_text())["enabled"] is False
    plist = home / "Library/LaunchAgents/com.arthur.repo-refresh.plist"
    schedule = plistlib.loads(plist.read_bytes())
    assert schedule["StartInterval"] == 60
    # A locally changed config no longer overrides the versioned feature setting.
    config.write_text(scenario.config.read_text())
    subprocess.run(command, check=True, capture_output=True)
    assert json.loads(config.read_text())["enabled"] is False
    enabled_command = [
        "chezmoi", "--source", str(ROOT), "--config", str(rendered.config),
        "--destination", str(home), "--override-data",
        json.dumps({"repoRefresh": {"enabled": True}, "reposDir": str(scenario.repo.parent)}),
        "apply", "--exclude", "scripts", "--force",
        str(config),
    ]
    subprocess.run(enabled_command, check=True, capture_output=True)
    assert json.loads(config.read_text()) == {
        "enabled": True, "root": str(scenario.repo.parent), "remote": "origin",
    }
    scenario.advance()

    result = subprocess.run([sys.executable, str(executable)], capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (scenario.repo / "upstream.txt").exists()


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_repo_refresh_switch_controls_config_and_agent_guidance(
        scenario, profile_factory, profile):
    rendered = profile_factory.render(profile)
    home = Path.home()
    config = home / ".config/repo-refresh/config.json"
    guidance = home / ".codex/AGENTS.md"
    guidance.parent.mkdir(parents=True, exist_ok=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    for enabled in (False, True, False):
        command = [
            "chezmoi", "--source", str(ROOT), "--config", str(rendered.config),
            "--destination", str(home), "--override-data",
            json.dumps({"repoRefresh": {"enabled": enabled}}),
            "apply", "--exclude", "scripts", "--force", str(config), str(guidance),
        ]

        result = subprocess.run(command, text=True, capture_output=True)

        assert result.returncode == 0, result.stderr
        assert json.loads(config.read_text())["enabled"] is enabled
        assert ("Automatic repository and worktree maintenance" in guidance.read_text()) is enabled
        assert "Creating or relocating a linked Git worktree" in guidance.read_text()


def test_install_hook_reconciles_enabled_state_and_loaded_revision(
        scenario, profile_factory, monkeypatch):
    rendered = profile_factory.render("personal")
    home = Path.home()
    destination = home / "Library/LaunchAgents/com.arthur.repo-refresh.plist"
    destination.parent.mkdir(parents=True)
    template = ROOT / "home/private_Library/private_LaunchAgents/com.arthur.repo-refresh.plist.tmpl"
    destination.write_text(profile_factory.chezmoi(
        rendered.config, "execute-template", "--file", str(template)))
    revision = plistlib.loads(destination.read_bytes())[
        "EnvironmentVariables"]["REPO_REFRESH_AGENT_REVISION"]
    hook = profile_factory.render_hook(rendered.config, "personal",
                                      "run_after_25-ensure-repo-refresh.sh.tmpl", "repo-refresh")
    fake_bin = home / "fake-bin"
    fake_bin.mkdir()
    service = home / "fake-service"
    service.mkdir()
    for name, contents in {
        "uname": "#!/bin/sh\necho Darwin\n",
        "plutil": "#!/bin/sh\nexit 0\n",
        "launchctl": """#!/bin/sh
set -eu
dir="$TEST_AGENT_DIR"
case "$1" in
  print)
    test -e "$dir/loaded" || exit 3
    printf 'REPO_REFRESH_AGENT_REVISION => %s\n' "$(cat "$dir/revision")"
    ;;
  enable)
    rm -f "$dir/disabled"
    printf 'enable\n' >> "$dir/actions"
    ;;
  disable)
    touch "$dir/disabled"
    printf 'disable\n' >> "$dir/actions"
    ;;
  bootstrap)
    test ! -e "$dir/disabled" || exit 10
    touch "$dir/loaded"
    printf '%s\n' "$TEST_DESIRED_REVISION" > "$dir/revision"
    printf 'bootstrap\n' >> "$dir/actions"
    ;;
  bootout)
    rm -f "$dir/loaded"
    printf 'bootout\n' >> "$dir/actions"
    ;;
  *)
    exit 97
    ;;
esac
""",
    }.items():
        command = fake_bin / name
        command.write_text(contents)
        command.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("TEST_AGENT_DIR", str(service))
    monkeypatch.setenv("TEST_DESIRED_REVISION", revision)
    config = home / ".config/repo-refresh/config.json"
    config.parent.mkdir(parents=True)
    marker = home / "Library/Caches/chezmoi/com.arthur.repo-refresh.sha256"

    def apply(enabled):
        config.write_text(json.dumps({"enabled": enabled}))
        return subprocess.run(["sh", str(hook)], capture_output=True, text=True)

    # Disabled applies persist and do not bootstrap an unloaded service.
    assert apply(False).returncode == 0
    assert (service / "disabled").is_file()
    assert not (service / "loaded").exists()
    assert not marker.exists()

    # Enable an already-disabled service, then repeat idempotently.
    assert apply(True).returncode == 0
    assert apply(True).returncode == 0
    assert not (service / "disabled").exists()
    assert (service / "loaded").is_file()
    assert marker.read_text().strip() == hashlib.sha256(destination.read_bytes()).hexdigest()

    # A running transaction blocks a restart rather than being terminated.
    (service / "revision").write_text("old-launchagent-definition\n")
    lock = home / ".local/state/repo-refresh/run.lock"
    lock.parent.mkdir(parents=True)
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        blocked = apply(True)
        assert blocked.returncode == 1
        assert "active refresh" in blocked.stderr
        assert (service / "loaded").exists()
    assert apply(True).returncode == 0

    # Disabling persists immediately, but never interrupts an active refresh.
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        blocked = apply(False)
        assert blocked.returncode == 1
        assert (service / "disabled").exists()
        assert (service / "loaded").exists()
    assert apply(False).returncode == 0
    assert apply(False).returncode == 0
    assert not (service / "loaded").exists()
    assert (service / "disabled").exists()
    assert not marker.exists()
    assert (service / "actions").read_text().splitlines() == [
        "disable", "enable", "bootstrap", "enable", "enable", "enable",
        "bootout", "bootstrap", "disable", "disable", "bootout", "disable",
    ]


@pytest.mark.skipif(sys.platform != "darwin" or os.environ.get("GITHUB_ACTIONS") != "true",
                    reason="Real launchd tests are restricted to ephemeral macOS CI")
def test_real_launchd_executes_installed_updater(scenario, profile_factory):
    rendered = profile_factory.render("personal")
    home = Path.home()
    subprocess.run(["chezmoi", "--source", str(ROOT), "--config", str(rendered.config),
                    "--destination", str(home), "apply", "--exclude", "scripts", "--force"],
                   check=True, capture_output=True)
    (home / ".config/repo-refresh/config.json").write_text(scenario.config.read_text())
    plist = home / "Library/LaunchAgents/com.arthur.repo-refresh.plist"
    payload = plistlib.loads(plist.read_bytes())
    payload["Label"] += ".test-" + str(os.getpid())
    payload["StartInterval"] = 2  # Exercise a real periodic tick without waiting a minute.
    # The production environment is tested, with synthetic Git identity/config only.
    payload["EnvironmentVariables"].update({key: os.environ[key] for key in (
        "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM",
    )})
    plist.write_bytes(plistlib.dumps(payload))
    (home / "Library/Logs").mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    git(scenario.repo, "switch", "-c", "feature")
    (scenario.repo / "tracked.txt").write_text("scheduler feature\n")
    git(scenario.repo, "add", ".")
    git(scenario.repo, "commit", "-m", "Scheduler feature")
    git(scenario.repo, "switch", "main")
    scenario.advance()
    try:
        subprocess.run(["launchctl", "bootstrap", domain, str(plist)], check=True, capture_output=True)
        deadline = time.monotonic() + 30
        status = home / ".local/state/repo-refresh/status.json"
        while not status.exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        assert status.exists()
        assert (scenario.repo / "upstream.txt").exists()
        assert git(scenario.repo, "branch", "--show-current") == "main"
        assert json.loads(status.read_text())["repositories"][0]["branches"][0]["state"] == "rebased"
        # Real launchd exposes the loaded generation used by the install hook.
        loaded = subprocess.run(["launchctl", "print", f"{domain}/{payload['Label']}"],
                                check=True, capture_output=True, text=True)
        revision = payload["EnvironmentVariables"]["REPO_REFRESH_AGENT_REVISION"]
        assert f"REPO_REFRESH_AGENT_REVISION => {revision}" in loaded.stdout
        (scenario.upstream / "tracked.txt").write_text("periodic update\n")
        git(scenario.upstream, "add", ".")
        git(scenario.upstream, "commit", "-m", "Periodic tick")
        git(scenario.upstream, "push", "origin", "HEAD")
        target = git(scenario.upstream, "rev-parse", "HEAD")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            outcomes = json.loads(status.read_text())["repositories"]
            if outcomes and outcomes[0].get("commit") == target:
                break
            time.sleep(0.2)
        assert (scenario.repo / "tracked.txt").read_text() == "periodic update\n"
        assert git(scenario.repo, "branch", "--show-current") == "main"
        branch = json.loads(status.read_text())["repositories"][0]["branches"][0]
        assert branch["state"] == "conflicts"
        assert git(Path(branch["worktree"]), "ls-files", "--unmerged")
    finally:
        subprocess.run(["launchctl", "bootout", f"{domain}/{payload['Label']}"], capture_output=True)
