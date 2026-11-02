"""GitHub/Bitbucket worktree routing and device-write-policy tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "home/dot_local"
BITBUCKET = SCRIPTS / "share/pr-navigation/bitbucket.py"
NAVIGATION = SCRIPTS / "bin/executable_git-pr"
INSTALL = ROOT / "src/install_vscode_pr_navigation.py"


@pytest.fixture(scope="module")
def nav():
    sys.path.insert(0, str(BITBUCKET.parent))
    from importlib.machinery import SourceFileLoader

    loader = SourceFileLoader("pr_navigation_test_module", str(NAVIGATION))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def installer():
    spec = importlib.util.spec_from_file_location("pr_navigation_installer_test", INSTALL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config(profile="personal", owner="ArthurZakirov", workspace=()):
    return dict(profile=profile, githubUsername=owner, reposRoot="/unused",
                bitbucketWritableWorkspaces=list(workspace))


def execute(*command, cwd=None):
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def test_remote_host_detection_and_profile_authorization(nav):
    github = ("github.com", "arthurzakirov", "dotfiles")
    bitbucket = ("bitbucket.org", "company", "backend")
    assert nav.remote_identity("git@github.com:ArthurZakirov/dotfiles.git") == github
    assert nav.remote_identity("https://github.com/ArthurZakirov/dotfiles.git") == github
    assert nav.remote_identity("git@bitbucket.org:company/backend.git") == bitbucket
    assert nav.remote_identity("https://user:token@github.com/ArthurZakirov/dotfiles") == github
    assert nav.remote_identity("git@gitlab.com:owner/repo.git") is None
    assert nav.authorized_push(config(), github)
    assert not nav.authorized_push(config("professional"), github)
    assert not nav.authorized_push(config(), bitbucket)
    assert not nav.authorized_push(config("professional"), bitbucket)
    assert nav.authorized_push(config("professional", workspace=["company"]), bitbucket)


def test_github_pr_uses_source_repository_and_branch(nav, monkeypatch):
    def fake_command(argv, **kwargs):
        assert argv == ["gh", "api", "repos/team/app/pulls/42"]
        return json.dumps({"head": {"repo": {"full_name": "forkuser/forkrepo"},
                                    "ref": "feat/deep/branch"}})
    monkeypatch.setattr(nav, "command", fake_command)
    assert nav.parse_url("https://github.com/team/app/pull/42/files") == (
        ("github.com", "forkuser", "forkrepo"), "feat/deep/branch")


def test_github_tree_branch_resolves_longest_existing_ref(nav, monkeypatch):
    def fake_command(argv, **kwargs):
        return ("abc\trefs/heads/main\n"
                "def\trefs/heads/feat/sub\n"
                "ghi\trefs/heads/feat\n")
    monkeypatch.setattr(nav, "command", fake_command)
    assert nav.parse_url("https://github.com/owner/repo/tree/feat/sub/src/file.py") == (
        ("github.com", "owner", "repo"), "feat/sub")


def test_existing_pr_on_professional_machine_is_read_only(nav, monkeypatch):
    commands = []
    def fake_command(argv, **kwargs):
        commands.append(argv)
        return json.dumps([{
            "url": "https://github.com/arthurzakirov/dotfiles/pull/5",
            "headRepositoryOwner": {"login": "ArthurZakirov"}
        }])
    monkeypatch.setattr(nav, "command", fake_command)
    result = nav.github_pr(Path("/unused"), "feat/one",
                           ("github.com", "arthurzakirov", "dotfiles"),
                           "origin", config("professional"))
    assert result.endswith("/pull/5")
    assert len(commands) == 1
    assert commands[0][0:3] == ["gh", "pr", "list"]


def test_no_github_pr_creation_on_professional_machine(nav, monkeypatch):
    calls = []
    def fake_command(argv, **kwargs):
        calls.append(argv)
        return "[]"
    monkeypatch.setattr(nav, "command", fake_command)
    with pytest.raises(nav.NavigationError, match="disabled"):
        nav.github_pr(Path("/unused"), "feat/one",
                      ("github.com", "arthurzakirov", "dotfiles"),
                      "origin", config("professional"))
    assert len(calls) == 1


def test_missing_remote_branch_cannot_push_without_matching_workspace(nav, monkeypatch):
    calls = []
    monkeypatch.setattr(nav, "git", lambda *args, **kwargs: calls.append(args) or "")
    with pytest.raises(nav.NavigationError, match="blocked"):
        nav.maybe_push(Path("/unused"), "feat/one",
                       ("bitbucket.org", "other", "internal"), "origin",
                       config("professional", workspace=["company"]))
    assert not any("push" in entry for entry in calls)


def test_real_linked_worktree_upsert_never_switches_primary(nav, tmp_path):
    bare = tmp_path / "server.git"
    seed = tmp_path / "seed"
    root = tmp_path / "Repos"
    repo = root / "demo"
    execute("git", "init", "--bare", str(bare))
    execute("git", "init", "--initial-branch=main", str(seed))
    execute("git", "config", "user.email", "test@example.test", cwd=seed)
    execute("git", "config", "user.name", "Test", cwd=seed)
    execute("git", "config", "commit.gpgsign", "false", cwd=seed)
    (seed / "README.md").write_text("main")
    execute("git", "add", "README.md", cwd=seed)
    execute("git", "commit", "-m", "initial", cwd=seed)
    execute("git", "remote", "add", "origin", str(bare), cwd=seed)
    execute("git", "push", "-u", "origin", "main", cwd=seed)
    execute("git", "symbolic-ref", "HEAD", "refs/heads/main", cwd=bare)
    execute("git", "switch", "-c", "feat/sub/branch", cwd=seed)
    (seed / "new.txt").write_text("feature")
    execute("git", "add", "new.txt", cwd=seed)
    execute("git", "commit", "-m", "feature", cwd=seed)
    execute("git", "push", "-u", "origin", "feat/sub/branch", cwd=seed)
    root.mkdir()
    execute("git", "clone", str(bare), str(repo))
    target = nav.ensure_worktree(repo, "origin", "feat/sub/branch")
    assert target == root / "demo.worktrees" / "feat-sub-branch"
    assert (target / "new.txt").read_text() == "feature"
    assert nav.ensure_worktree(repo, "origin", "feat/sub/branch") == target
    assert execute("git", "branch", "--show-current", cwd=repo) == "main"
    assert execute("git", "branch", "--show-current", cwd=target) == "feat/sub/branch"
    assert sum(1 for _, branch in nav.worktree_records(repo)
               if branch == "feat/sub/branch") == 1


def test_vscode_installer_migrates_tasks_preserving_others(installer, tmp_path):
    user = tmp_path / "Code/User"
    user.mkdir(parents=True)
    (user / "tasks.json").write_text(json.dumps({
        "version": "2.0.0", "tasks": [
            {"label": "Bitbucket: Open Current Pull Request in Chrome", "type": "process",
             "command": "legacy"},
            {"label": "Unrelated Task", "command": "keep"},
        ]}))
    (user / "keybindings.json").write_text(
        '// My shortcut header\n[{"key":"ctrl+p ctrl+r",'
        '"command":"workbench.action.tasks.runTask",'
        '"args":"Bitbucket: Open Current Pull Request in Chrome",},'
        '{"key":"ctrl+q","command":"some.other.action"}]\n')
    installer.install(user)
    tasks = json.loads((user / "tasks.json").read_text())["tasks"]
    keys = json.loads(installer.strip_jsonc((user / "keybindings.json").read_text()))
    assert any(task["label"] == "Unrelated Task" and task["command"] == "keep"
               for task in tasks)
    assert sum(task["label"] == installer.TASK_LABEL for task in tasks) == 1
    assert sum(task["label"] == installer.BRANCH_LABEL for task in tasks) == 1
    assert keys[0]["args"] == installer.TASK_LABEL
    assert keys[1]["key"] == "ctrl+q"
    before = tuple((user / name).read_bytes() for name in ("tasks.json", "keybindings.json"))
    installer.install(user)
    assert tuple((user / name).read_bytes() for name in ("tasks.json", "keybindings.json")) == before
