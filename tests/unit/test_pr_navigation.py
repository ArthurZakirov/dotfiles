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
        "Unrelated Task", installer.TASK_LABEL, installer.BRANCH_LABEL,
        installer.REVIEW_CLEANUP_LABEL, installer.SESSIONS_LABEL,
    }
    assert {item["key"] for item in keys} == {
        "ctrl+x", "ctrl+p ctrl+r", installer.SESSIONS_KEY
    }
    task = next(item for item in tasks if item["label"] == installer.SESSIONS_LABEL)
    assert task["command"] == "${userHome}/.local/bin/find-gpt-session"
    assert task["args"] == ["--open", "--context-path", "${workspaceFolder}"]

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
    cleanup = [task for task in tasks if task["label"] == installer.REVIEW_CLEANUP_LABEL]
    assert cleanup == [installer.review_cleanup_task()]
    assert keys[0]["args"] == installer.TASK_LABEL
    assert keys[1]["key"] == "ctrl+q"
    before = tuple((user / name).read_bytes() for name in ("tasks.json", "keybindings.json"))
    installer.install(user)
    assert tuple((user / name).read_bytes() for name in ("tasks.json", "keybindings.json")) == before


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://bitbucket.org/team/app/pull-requests/42#comment-8192",
         ("src/service.py", 73)),
        ("https://bitbucket.org/team/app/pull-requests/42#comment-8193",
         ("src/deleted.py", None)),
    ],
    ids=["new-side-line", "deleted-side-has-no-current-line"],
)
def test_bitbucket_comment_permalink_resolves_inline_file_and_line(
    nav, monkeypatch, url, expected,
):
    responses = {
        8192: {"id": 8192, "inline": {"path": "src/service.py", "to": 73, "from": None}},
        8193: {"id": 8193, "inline": {"path": "src/deleted.py", "to": None, "from": 91}},
    }
    requests = []
    monkeypatch.setattr(nav.bitbucket, "bitbucket_tab", lambda _: (1, 2))

    def fake_api(tab, endpoint):
        requests.append((tab, endpoint))
        return responses[int(endpoint.rsplit("/", 1)[-1])]

    monkeypatch.setattr(nav.bitbucket, "browser_api", fake_api)

    location = nav.bitbucket.comment_location(url)

    assert location == expected
    assert requests == [
        ((1, 2), "/!api/2.0/repositories/team/app/pullrequests/42/comments/"
         + url.rsplit("-", 1)[-1]),
    ]


def test_bitbucket_comment_reply_uses_original_inline_anchor(nav, monkeypatch):
    responses = {
        8194: {"id": 8194, "parent": {"id": 8192}},
        8192: {"id": 8192, "inline": {"path": "src/service.py", "to": 73}},
    }
    monkeypatch.setattr(nav.bitbucket, "bitbucket_tab", lambda _: (1, 2))
    monkeypatch.setattr(nav.bitbucket, "browser_api",
                        lambda tab, endpoint: responses[int(endpoint.rsplit("/", 1)[-1])])

    location = nav.bitbucket.comment_location(
        "https://bitbucket.org/team/app/pull-requests/42#comment-8194"
    )

    assert location == ("src/service.py", 73)


@pytest.mark.parametrize(
    ("comment", "error"),
    [
        ({"id": 1, "inline": None}, "not attached"),
        ({"id": 1, "parent": {"id": 1}}, "cycle"),
        ({"id": 2, "inline": {"path": "src/a.py", "to": 12}}, "different comment"),
        ({"id": 1, "inline": {"path": "src/a.py", "to": -3}},
         None),
    ],
    ids=["general-pr-comment", "cyclic-reply", "wrong-comment-id", "invalid-new-line"],
)
def test_bitbucket_comment_location_handles_missing_or_invalid_anchors(
    nav, monkeypatch, comment, error,
):
    monkeypatch.setattr(nav.bitbucket, "bitbucket_tab", lambda _: (1, 2))
    monkeypatch.setattr(nav.bitbucket, "browser_api", lambda *_: comment)
    url = "https://bitbucket.org/team/app/pull-requests/42#comment-1"

    if error:
        with pytest.raises(nav.bitbucket.NavigationError, match=error):
            nav.bitbucket.comment_location(url)
    else:
        assert nav.bitbucket.comment_location(url) == ("src/a.py", None)


def test_non_comment_bitbucket_url_does_not_lookup_comment(nav, monkeypatch):
    monkeypatch.setattr(nav.bitbucket, "bitbucket_tab",
                        lambda _: pytest.fail("Ordinary PR must not request a comment"))

    assert nav.bitbucket.comment_location(
        "https://bitbucket.org/team/app/pull-requests/42"
    ) is None
    assert nav.bitbucket.comment_location(
        "https://bitbucket.org/team/app/pull-requests/42#activity"
    ) is None

    with pytest.raises(nav.bitbucket.NavigationError, match="Invalid.*permalink"):
        nav.bitbucket.comment_location(
            "https://bitbucket.org/team/app/pull-requests/42#comment-../../no"
        )


@pytest.mark.parametrize(
    "relative_path",
    ["/tmp/outside.py", "../outside.py", "src/../../outside.py",
     "src\\outside.py", "src/missing.py", "", "src/unsafe" + chr(0) + ".py"],
)
def test_bitbucket_comment_cannot_open_file_outside_worktree(
    nav, tmp_path, relative_path,
):
    target = tmp_path / "worktree"
    (target / "src").mkdir(parents=True)
    (target / "src/exists.py").write_text("pass")
    with pytest.raises(nav.NavigationError, match="(invalid|escapes|no longer)"):
        nav.comment_file(target, relative_path)


def test_bitbucket_comment_rejects_symlink_escaping_worktree(nav, tmp_path):
    target = tmp_path / "worktree"
    target.mkdir()
    external = tmp_path / "secret.py"
    external.write_text("private = True")
    (target / "source.py").symlink_to(external)

    with pytest.raises(nav.NavigationError, match="escapes"):
        nav.comment_file(target, "source.py")


@pytest.mark.parametrize(
    ("anchor", "expected_suffix"),
    [
        (("src/service.py", 27), ("--goto", "src/service.py:27")),
        (("src/service.py", None), ("src/service.py",)),
        (None, ()),
    ],
    ids=["line-in-code", "file-only-for-old-side", "ordinary-pr-opens-worktree"],
)
def test_bitbucket_pr_comment_opens_vscode_at_requested_file(
    nav, monkeypatch, tmp_path, anchor, expected_suffix,
):
    target = tmp_path / "source"
    execute("git", "init", "-b", "feat/review", str(target))
    (target / "src").mkdir()
    (target / "src/service.py").write_text("def service():\\n    return 1\\n")

    url = "https://bitbucket.org/team/app/pull-requests/42"
    if anchor is not None:
        url += "#comment-8192"

    monkeypatch.setattr(nav.bitbucket, "source_branch_url",
                        lambda _: "https://bitbucket.org/team/app/branch/feat%2Freview")
    monkeypatch.setattr(nav.bitbucket, "comment_location", lambda _: anchor)
    monkeypatch.setattr(nav, "ensure_repo", lambda *args: (target, "origin"))
    monkeypatch.setattr(nav, "ensure_worktree", lambda *args: target)
    monkeypatch.setattr(nav.shutil, "which", lambda _: "/usr/local/bin/code")

    actual_command = nav.command
    vscode_calls = []

    def fake_command(argv, **kwargs):
        if argv[0] == "/usr/local/bin/code":
            vscode_calls.append(argv)
            return ""
        return actual_command(argv, **kwargs)

    monkeypatch.setattr(nav, "command", fake_command)

    result = nav.open_local(url, config("professional"), tmp_path, print_only=False)

    assert result == target
    expected = ["/usr/local/bin/code", "--new-window", str(target)]
    if len(expected_suffix) == 2:
        expected += ["--goto", str(target / "src/service.py") + ":27"]
    elif len(expected_suffix) == 1:
        expected.append(str(target / "src/service.py"))
    assert vscode_calls == [expected]


@pytest.mark.parametrize(
    "remote",
    [
        "git@ssh.bitbucket.org:Company/Backend.git",
        "ssh://git@ssh.bitbucket.org/Company/Backend.git",
        "ssh://git@ssh.bitbucket.org:22/Company/Backend.git",
        "git@bitbucket.org:Company/Backend.git",
        "ssh://git@bitbucket.org/Company/Backend.git",
        "ssh://git@altssh.bitbucket.org:443/Company/Backend.git",
        "https://bitbucket.org/Company/Backend.git",
    ],
    ids=[
        "new-scp", "new-ssh-url", "new-ssh-port", "legacy-scp",
        "legacy-ssh-url", "alternative-ssh-port-443", "unchanged-https",
    ],
)
def test_bitbucket_git_transport_urls_share_repository_identity(nav, remote):
    expected = ("bitbucket.org", "company", "backend")

    assert nav.remote_identity(remote) == expected
    assert nav.bitbucket.repository_identity(remote) == expected[1:]


@pytest.mark.parametrize(
    "remote",
    [
        "git@ssh.bitbucket.com:company/backend.git",
        "ssh://git@evil.bitbucket.org/company/backend.git",
        "https://ssh.bitbucket.org/company/backend.git",
        "https://altssh.bitbucket.org/company/backend.git",
        "git@github.com:company/backend.git",
    ],
)
def test_bitbucket_remote_identity_rejects_untrusted_or_other_hosts(nav, remote):
    assert nav.bitbucket.repository_identity(remote) is None
    if "github.com" not in remote:
        assert nav.remote_identity(remote) is None


def test_git_pr_generates_new_bitbucket_ssh_url_without_changing_browser_urls(nav):
    identity = ("bitbucket.org", "company", "backend")

    assert nav.remote_url(*identity) == "git@ssh.bitbucket.org:company/backend.git"
    assert nav.remote_url("github.com", "owner", "repo") == "git@github.com:owner/repo.git"
    assert nav.branch_page(identity, "feat/test") == (
        "https://bitbucket.org/company/backend/branch/feat%2Ftest"
    )


def test_new_bitbucket_ssh_remote_reuses_existing_primary_checkout(
    nav, tmp_path, monkeypatch,
):
    root = tmp_path / "Repos"
    repo = root / "backend"
    root.mkdir()
    execute("git", "init", "-b", "feat/review", str(repo))
    execute(
        "git", "remote", "add", "origin",
        "git@ssh.bitbucket.org:company/backend.git", cwd=repo,
    )
    identity = ("bitbucket.org", "company", "backend")

    assert nav.find_repo(root, identity) == (repo, "origin")
    assert nav.ensure_repo(root, identity, config("professional")) == (repo, "origin")
    assert nav.current_branch(repo) == ("feat/review", identity, "origin")
    assert nav.bitbucket.remotes(repo) == {"origin": ("company", "backend")}
    assert nav.bitbucket.branch_url(repo) == (
        "https://bitbucket.org/company/backend/branch/feat%2Freview"
    )

    monkeypatch.setattr(nav.bitbucket, "source_branch_url", lambda url: (
        "https://bitbucket.org/company/backend/branch/feat%2Freview"
    ))
    monkeypatch.setattr(nav, "ensure_worktree", lambda *args: repo)
    result = nav.open_local(
        "https://bitbucket.org/company/backend/pull-requests/42",
        config("professional"), root, print_only=True,
    )

    assert result == repo
    assert execute(
        "git", "config", "--get", "branch.feat/review.prDestination", cwd=repo,
    ) == "git@ssh.bitbucket.org:company/backend.git"
