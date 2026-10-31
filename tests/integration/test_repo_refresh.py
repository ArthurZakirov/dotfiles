"""CLI-to-filesystem tests using real Git and disposable local remotes only."""

from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import plistlib
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
    repo = root / "personal" / "project"
    repo.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(remote), str(repo)], check=True, capture_output=True)
    config = tmp_path / "config.json"
    worktrees = tmp_path / "Worktrees"
    config.write_text(json.dumps({"root": str(root), "worktrees": str(worktrees)}))
    return Scenario(repo, upstream, remote, config, tmp_path / "state", worktrees)


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
    assert git(recovery, "branch", "--show-current") == (branch if branch and branch != "main" else "")


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
    scenario.worktrees.mkdir()
    (scenario.worktrees / "personal").symlink_to(scenario.repo)

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 1
    assert git(scenario.repo, "branch", "--show-current") == "feature"
    assert not (scenario.repo / "project").exists()


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
    root = tmp_path / "unborn"
    root.mkdir()
    git(root, "init", "-b", "unfinished")
    git(root, "remote", "add", "origin", scenario.remote)
    (root / "local.txt").write_text("first staged file\n")
    git(root, "add", ".")
    config = json.loads(scenario.config.read_text())
    config["root"] = str(root)
    scenario.config.write_text(json.dumps(config))

    result = subprocess.run(scenario.command, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert git(root, "branch", "--show-current") == "main"
    recovery = Path(scenario.outcome()["recovery"])
    assert (recovery / "local.txt").read_text() == "first staged file\n"
    assert git(recovery, "show", ":local.txt") == "first staged file"
    assert git(recovery, "branch", "--show-current") == "unfinished"


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


@pytest.mark.parametrize("mode", ["disabled", "overlap", "locked", "empty-root", "invalid-enabled"])
def test_configuration_and_run_lock_prevent_mutation(scenario, mode):
    git(scenario.repo, "switch", "-c", "feature")
    config = json.loads(scenario.config.read_text())
    handle = None
    if mode == "disabled":
        config["enabled"] = False
    elif mode == "overlap":
        config["worktrees"] = str(scenario.repo / "recovery")
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

    assert result.returncode == (1 if mode in ("overlap", "empty-root", "invalid-enabled") else 0)
    assert git(scenario.repo, "branch", "--show-current") == "feature"
    assert not scenario.worktrees.exists()


def test_chezmoi_installs_executable_schedule_and_preserves_local_configuration(scenario, profile_factory):
    rendered = profile_factory.render("personal")
    home = Path.home()  # scenario fixture supplies a disposable HOME
    command = ["chezmoi", "--source", str(ROOT), "--config", str(rendered.config),
               "--destination", str(home), "apply", "--exclude", "scripts", "--force"]

    subprocess.run(command, check=True, capture_output=True)

    executable = home / ".local/bin/repo-refresh"
    assert os.access(executable, os.X_OK)
    config = home / ".config/repo-refresh/config.json"
    assert json.loads(config.read_text())["enabled"] is True
    plist = home / "Library/LaunchAgents/com.arthur.repo-refresh.plist"
    schedule = plistlib.loads(plist.read_bytes())
    assert schedule["StartInterval"] == 60
    config.write_text(scenario.config.read_text())
    subprocess.run(command, check=True, capture_output=True)
    assert config.read_text() == scenario.config.read_text()
    scenario.advance()

    result = subprocess.run([sys.executable, str(executable)], capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (scenario.repo / "upstream.txt").exists()


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
    payload["EnvironmentVariables"].update({key: value for key, value in os.environ.items()
                                            if key.startswith("GIT_")})
    plist.write_bytes(plistlib.dumps(payload))
    (home / "Library/Logs").mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
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
    finally:
        subprocess.run(["launchctl", "bootout", f"{domain}/{payload['Label']}"], capture_output=True)
