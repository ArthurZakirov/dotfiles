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


def config(profile="personal", owner="ArthurZakirov"):
    return dict(profile=profile, githubUsername=owner, reposRoot="/unused")


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
    assert nav.authorized_push(config("professional"), bitbucket)
    assert nav.authorized_push(config("professional"), ("bitbucket.org", "another-team", "other-repo"))


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


def test_missing_remote_bitbucket_branch_is_pushed_on_professional_mac(nav, monkeypatch):
    calls = []

    def fake_git(repo, *args, **kwargs):
        calls.append(args)
        return ""

    monkeypatch.setattr(nav, "git", fake_git)
    nav.maybe_push(Path("/unused"), "feat/one",
                   ("bitbucket.org", "any-company-team", "internal"), "origin",
                   config("professional"))
    assert calls == [
        ("ls-remote", "--heads", "origin", "refs/heads/feat/one"),
        ("push", "--set-upstream", "origin", "refs/heads/feat/one"),
    ]


def test_personal_machine_still_cannot_push_bitbucket_branch(nav, monkeypatch):
    calls = []
    monkeypatch.setattr(nav, "git", lambda *args, **kwargs: calls.append(args) or "")
    with pytest.raises(nav.NavigationError, match="blocked"):
        nav.maybe_push(Path("/unused"), "feat/one",
                       ("bitbucket.org", "company", "internal"), "origin",
                       config("personal"))
    assert not any("push" in entry for entry in calls)


def test_existing_remote_bitbucket_branch_is_never_pushed_again(nav, monkeypatch):
    calls = []

    def fake_git(repo, *args, **kwargs):
        calls.append(args)
        return "abc123\trefs/heads/feat/one"

    monkeypatch.setattr(nav, "git", fake_git)
    nav.maybe_push(Path("/unused"), "feat/one",
                   ("bitbucket.org", "company", "internal"), "origin",
                   config("professional"))
    assert len(calls) == 1
    assert calls[0][0] == "ls-remote"


def test_bitbucket_shortcut_pushes_missing_branch_but_never_creates_pr(nav, monkeypatch):
    repo = Path("/unused")
    identity = ("bitbucket.org", "any-company-team", "internal")
    pushes = []

    monkeypatch.setattr(nav, "current_branch", lambda _: ("feat/new", identity, "origin"))
    monkeypatch.setattr(nav, "pr_destination", lambda repo, branch, source: source)
    monkeypatch.setattr(nav.bitbucket, "open_pull_requests", lambda url, **kwargs: [])
    monkeypatch.setattr(nav, "maybe_push",
                        lambda *args: pushes.append(args))
    monkeypatch.setattr(nav, "open_chrome",
                        lambda _: pytest.fail("print-only should not open Chrome"))
    url = nav.open_pr(repo, config("professional"), print_only=True)
    assert url == "https://bitbucket.org/any-company-team/internal/branch/feat%2Fnew"
    assert pushes == [(repo, "feat/new", identity, "origin", config("professional"))]


def test_bitbucket_shortcut_reuses_existing_pr_without_push(nav, monkeypatch):
    identity = ("bitbucket.org", "team", "repo")
    monkeypatch.setattr(nav, "current_branch",
                        lambda _: ("feat/existing", identity, "origin"))
    monkeypatch.setattr(nav, "pr_destination", lambda repo, branch, source: source)
    monkeypatch.setattr(nav.bitbucket, "open_pull_requests",
                        lambda url, **kwargs: [{"url": "https://bitbucket.org/team/repo/pull-requests/12"}])
    monkeypatch.setattr(nav, "maybe_push",
                        lambda *args: pytest.fail("Existing PR must never trigger push"))
    assert nav.open_pr(Path("/unused"), config("professional"), print_only=True) == (
        "https://bitbucket.org/team/repo/pull-requests/12")


def test_github_fork_pr_round_trip_uses_destination_repo(nav, monkeypatch, tmp_path):
    repo = tmp_path / "forkrepo"
    execute("git", "init", "-b", "feat/roundtrip", str(repo))
    execute("git", "remote", "add", "origin", "git@github.com:forkuser/forkrepo.git", cwd=repo)
    pr_url = "https://github.com/team/app/pull/42"
    calls = []
    actual_command = nav.command

    def fake_command(argv, **kwargs):
        if argv[:2] == ["gh", "api"]:
            return json.dumps({"head": {
                "repo": {"full_name": "forkuser/forkrepo"}, "ref": "feat/roundtrip"
            }})
        if argv[:3] == ["gh", "pr", "list"]:
            calls.append(argv)
            return json.dumps([{
                "url": pr_url, "headRepositoryOwner": {"login": "forkuser"}
            }])
        return actual_command(argv, **kwargs)

    monkeypatch.setattr(nav, "command", fake_command)
    monkeypatch.setattr(nav, "ensure_repo", lambda *args: (repo, "origin"))
    monkeypatch.setattr(nav, "ensure_worktree", lambda *args: repo)
    monkeypatch.setattr(nav, "maybe_push",
                        lambda *args: pytest.fail("Existing PR must not be pushed"))

    # Browser PR -> source-fork worktree -> same destination PR.
    assert nav.open_local(pr_url, config("professional"), tmp_path,
                          print_only=True) == repo
    assert execute("git", "config", "--get", "branch.feat/roundtrip.prDestination",
                   cwd=repo) == "git@github.com:team/app.git"
    assert nav.open_pr(repo, config("professional"), print_only=True) == pr_url
    assert len(calls) == 1
    assert calls[0][calls[0].index("--repo") + 1] == "team/app"


def test_github_fork_pr_creation_targets_destination(nav, monkeypatch, tmp_path):
    repo = tmp_path / "forkrepo"
    execute("git", "init", "-b", "feat/new", str(repo))
    execute("git", "remote", "add", "origin", "git@github.com:forkuser/forkrepo.git", cwd=repo)
    execute("git", "config", "branch.feat/new.prDestination",
            "git@github.com:team/app.git", cwd=repo)
    actual_command = nav.command
    outbound = []

    def fake_command(argv, **kwargs):
        if argv[:3] == ["gh", "pr", "list"]:
            outbound.append(argv)
            return "[]"
        if argv[:3] == ["gh", "pr", "create"]:
            outbound.append(argv)
            return "https://github.com/team/app/pull/51"
        return actual_command(argv, **kwargs)

    monkeypatch.setattr(nav, "command", fake_command)
    monkeypatch.setattr(nav, "maybe_push", lambda *args: None)

    assert nav.open_pr(repo, config("personal", owner="forkuser"),
                       print_only=True) == "https://github.com/team/app/pull/51"
    assert outbound[0][outbound[0].index("--repo") + 1] == "team/app"
    assert outbound[1][outbound[1].index("--repo") + 1] == "team/app"
    assert outbound[1][outbound[1].index("--head") + 1] == "forkuser:feat/new"


def test_bitbucket_fork_pr_round_trip_queries_destination(nav, monkeypatch, tmp_path):
    repo = tmp_path / "forkrepo"
    execute("git", "init", "-b", "feat/roundtrip", str(repo))
    execute("git", "remote", "add", "origin", "git@bitbucket.org:forkuser/forkrepo.git",
            cwd=repo)
    pr_url = "https://bitbucket.org/team/app/pull-requests/42"
    monkeypatch.setattr(nav.bitbucket, "source_branch_url",
                        lambda _: "https://bitbucket.org/forkuser/forkrepo/branch/feat%2Froundtrip")
    monkeypatch.setattr(nav, "ensure_repo", lambda *args: (repo, "origin"))
    monkeypatch.setattr(nav, "ensure_worktree", lambda *args: repo)
    monkeypatch.setattr(nav.bitbucket, "bitbucket_tab", lambda _: (1, 2))
    monkeypatch.setattr(nav, "maybe_push",
                        lambda *args: pytest.fail("Existing PR must not be pushed"))
    api_paths = []

    def fake_browser_api(tab, endpoint):
        api_paths.append(endpoint)
        return {"values": [{
            "id": 42,
            "title": "Feature",
            "source": {"branch": {"name": "feat/roundtrip"},
                       "repository": {"full_name": "forkuser/forkrepo"}},
            "destination": {"branch": {"name": "main"}},
        }]}

    monkeypatch.setattr(nav.bitbucket, "browser_api", fake_browser_api)

    assert nav.open_local(pr_url, config("professional"), tmp_path,
                          print_only=True) == repo
    assert nav.open_pr(repo, config("professional"), print_only=True) == pr_url
    assert len(api_paths) == 1
    assert api_paths[0].startswith("/!api/2.0/repositories/team/app/pullrequests?")
    assert "forkuser%2Fforkrepo" in api_paths[0]


def test_installer_handles_jsonc_trailing_commas_and_repeated_apply(installer, tmp_path):
    user = tmp_path / "Code/User"
    user.mkdir(parents=True)
    tasks_file = user / "tasks.json"
    keys_file = user / "keybindings.json"
    tasks_file.write_text(
        '{\n "version": "2.0.0",\n "tasks": [\n'
        '  {"label": "Unrelated Task", "command": "echo"}, // keep task\n'
        ' ]\n}\n'
    )
    keys_file.write_text(
        '[\n {"key": "ctrl+x", "command": "unrelated"}, // keep binding\n]\n'
    )

    installer.install(user)

    tasks_source, keys_source = tasks_file.read_text(), keys_file.read_text()
    tasks = json.loads(installer.strip_jsonc(tasks_source))["tasks"]
    keys = json.loads(installer.strip_jsonc(keys_source))
    assert "// keep task" in tasks_source
    assert "// keep binding" in keys_source
    assert {item["label"] for item in tasks} == {
        "Unrelated Task", installer.TASK_LABEL, installer.BRANCH_LABEL
    }
    assert {item["key"] for item in keys} == {"ctrl+x", "ctrl+p ctrl+r"}

    installer.install(user)
    assert (tasks_file.read_text(), keys_file.read_text()) == (tasks_source, keys_source)


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
