"""Real-Git end-to-end coverage of the installed Git review aliases.

No mocks for Git: every test invokes the same aliases and helper shipped to Macs.
Only the VS Code launcher is replaced to prevent opening editor windows in CI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "home/dot_local/bin/executable_git-review-worktree"
CONFIG = ROOT / "home/dot_gitconfig"


@pytest.fixture
def sandbox(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_bytes(CONFIG.read_bytes())
    (home / ".gitconfig.local").write_text("")
    binary = home / ".local/bin"
    binary.mkdir(parents=True)
    shutil.copy2(HELPER, binary / "git-review-worktree")
    (binary / "git-review-worktree").chmod(0o755)
    launcher = tmp_path / "bin"
    launcher.mkdir()
    code = launcher / "code"
    code.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$1\" \"$2\" >> \"$REVIEW_CODE_LOG\"\n"
        'env | grep -E "^GIT_(DIR|WORK_TREE|PREFIX|INDEX_FILE|COMMON_DIR|OBJECT_DIRECTORY|CONFIG_PARAMETERS)=" >> "$REVIEW_CODE_ENV_LOG" || true\n'
        'exit "${REVIEW_CODE_EXIT:-0}"\n'
    )
    code.chmod(0o755)
    env = {
        **{key: value for key, value in os.environ.items() if key not in (
            "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_PREFIX", "GIT_CEILING_DIRECTORIES", "GIT_CONFIG_PARAMETERS",
        )},
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_COUNT": "0",
        "REVIEW_CODE_LOG": str(tmp_path / "code.log"),
        "REVIEW_CODE_ENV_LOG": str(tmp_path / "code-env.log"),
        "PATH": f"{launcher}{os.pathsep}{binary}{os.pathsep}{os.environ['PATH']}",
    }
    source = tmp_path / "source"
    source.mkdir()

    def git(*args, cwd=None, check=True, env_override=None):
        return subprocess.run(
            ["git", *map(str, args)],
            cwd=cwd or source,
            env={**env, **(env_override or {})},
            check=check,
            capture_output=True,
            text=True,
        )

    git("init", "-q")
    git("branch", "-M", "main")
    git("config", "user.name", "Review Test")
    git("config", "user.email", "review@example.invalid")
    git("config", "commit.gpgsign", "false")
    return source, home, env, git


def commit(git, message):
    git("add", "-A")
    git("commit", "-m", message, "-q")
    return git("rev-parse", "HEAD").stdout.strip()


def review_path(result):
    assert result.returncode == 0, result.stderr
    path = Path(result.stdout.strip().splitlines()[-1])
    assert path.is_dir(), (result.stdout, result.stderr)
    return path


def assert_review(source, home, git, review, base, expected_files):
    assert review.is_relative_to(home / ".local/share/git-review")
    assert git("rev-parse", "HEAD", cwd=review).stdout.strip() == base
    assert git("diff", "--cached", "--name-only", cwd=review).stdout.strip() == ""
    for path, data in expected_files.items():
        actual = review / path
        if data is None:
            assert not actual.exists(), path
        else:
            assert actual.read_bytes() == data, path
    listed = git("worktree", "list", "--porcelain").stdout
    assert f"worktree {review}\n" in listed
    assert git("status", "--porcelain", cwd=review).stdout.strip()
    assert (source / ".git").is_dir()
    # The title is derived from the source repository and target commit, not
    # the random temporary review directory. It does not pollute Git status.
    git_dir = Path(git("rev-parse", "--path-format=absolute", "--git-dir", cwd=review).stdout.strip())
    target = json.loads((git_dir / "GIT_REVIEW.json").read_text())["target"]
    workspace = review.parent / "workspaces" / review.name / f"{source.name} · review · {target[:7]}.code-workspace"
    assert workspace.is_file()
    assert json.loads(workspace.read_text()) == {
        "folders": [{"name": f"{source.name} · review", "path": str(review)}],
    }
    assert workspace.parent != review
    assert not workspace.is_relative_to(source)
    assert not workspace.is_relative_to(source / ".git")
    assert not workspace.is_relative_to(review)
    # VS Code must not find the original repo by searching upward from the
    # workspace file. This was the cause of duplicate Source Control entries.
    assert git("rev-parse", "--show-toplevel", cwd=workspace.parent, check=False).returncode != 0
    assert workspace.name not in git("status", "--porcelain", cwd=review).stdout


def assert_cleanup(source, git, review):
    git("unreview", cwd=review)
    assert not review.exists()
    assert not (review.parent / "workspaces" / review.name).exists()
    assert str(review) not in git("worktree", "list").stdout
    assert git("status", "--porcelain").stdout == ""


@pytest.mark.parametrize("command", ["review", "review-range"])
def test_complex_commit_round_trip_uses_real_aliases(sandbox, command):
    source, home, env, git = sandbox
    (source / "original.txt").write_text("rename me\n")
    (source / "deleted.txt").write_text("remove\n")
    (source / "modified.txt").write_text("old\n")
    (source / "binary.bin").write_bytes(b"\x00\x01\x02\xff")
    executable = source / "script.sh"
    executable.write_text("#!/bin/sh\necho before\n")
    executable.chmod(0o644)
    base = commit(git, "base")

    git("mv", "original.txt", "renamed.txt")
    (source / "deleted.txt").unlink()
    (source / "modified.txt").write_text("new\n")
    (source / "binary.bin").write_bytes(b"\x00\xfe\xff\x03")
    (source / "added file.txt").write_text("new file\n")
    executable.write_text("#!/bin/sh\necho after\n")
    executable.chmod(0o755)
    target = commit(git, "target")
    # The source checkout has ongoing changes; review must never modify them.
    (source / "modified.txt").write_text("uncommitted source edit\n")
    (source / "scratch.txt").write_text("untracked\n")
    before = git("status", "--porcelain").stdout
    args = ("review", target) if command == "review" else ("review-range", base, target)
    review = review_path(git(*args))
    assert_review(
        source, home, git, review, base,
        {
            "renamed.txt": b"rename me\n",
            "original.txt": None,
            "deleted.txt": None,
            "modified.txt": b"new\n",
            "binary.bin": b"\x00\xfe\xff\x03",
            "added file.txt": b"new file\n",
            "script.sh": b"#!/bin/sh\necho after\n",
        },
    )
    assert (review / "script.sh").stat().st_mode & 0o111
    assert git("status", "--porcelain").stdout == before
    assert git("rev-parse", "HEAD").stdout.strip() == target
    assert (source / "modified.txt").read_text() == "uncommitted source edit\n"
    assert (source / "scratch.txt").read_text() == "untracked\n"
    git_dir = Path(git("rev-parse", "--path-format=absolute", "--git-dir", cwd=review).stdout.strip())
    workspace = review.parent / "workspaces" / review.name / f"{source.name} · review · {target[:7]}.code-workspace"
    assert Path(env["REVIEW_CODE_LOG"]).read_text().splitlines() == ["-r", str(workspace)]
    assert Path(env["REVIEW_CODE_ENV_LOG"]).read_text() == "", "VS Code inherited local Git environment"

    # From the review, return to the original checkout without losing source edits.
    git("unreview", cwd=review)
    assert not review.exists()
    assert not (review.parent / "workspaces" / review.name).exists()
    assert str(review) not in git("worktree", "list").stdout
    assert git("status", "--porcelain").stdout == before
    assert Path(env["REVIEW_CODE_LOG"]).read_text().splitlines() == [
        "-r", str(workspace), "-r", str(source)
    ]


def test_vscode_does_not_inherit_git_alias_repository_environment(sandbox):
    """VS Code must not receive repository-local vars from a shell Git alias.

    This regression previously made the Git extension display the same branch
    for several unrelated subdirectories as separate Source Control entries.
    """
    source, home, env, git = sandbox
    (source / "a.txt").write_text("old\n")
    commit(git, "base")
    (source / "a.txt").write_text("new\n")
    target = commit(git, "target")
    repo_git_dir = source / ".git"
    review = review_path(git("review", "HEAD", env_override={
        "GIT_DIR": str(repo_git_dir),
        "GIT_WORK_TREE": str(source),
        "GIT_PREFIX": "nested/",
        "GIT_INDEX_FILE": str(repo_git_dir / "index"),
        "GIT_COMMON_DIR": str(repo_git_dir),
    }))
    # The real alias is used; only VS Code is replaced with an env-recording
    # stub, so this catches leakage at the subprocess boundary.
    assert Path(env["REVIEW_CODE_ENV_LOG"]).read_text() == ""
    assert git("rev-parse", "HEAD", cwd=review).stdout.strip() != target
    assert_cleanup(source, git, review)


def test_checkout_filter_and_crlf_do_not_break_review(sandbox):
    """A smudge filter makes index blobs differ from checkout bytes.

    The previous git apply --index implementation rejected this state with
    'does not match index'; reset-based materialization supports it.
    """
    source, home, env, git = sandbox
    (source / ".gitattributes").write_text(
        "filtered.txt filter=reviewtest\ncrlf.txt text eol=crlf\n"
    )
    (source / "filtered.txt").write_text("hello old\n")
    (source / "crlf.txt").write_text("before\n")
    base = commit(git, "base")
    (source / "filtered.txt").write_text("hello new\n")
    (source / "crlf.txt").write_text("after\n")
    target = commit(git, "target")

    # Configure only after committing, so the test commit blobs are canonical.
    # Both the temporary worktree and source share the repository configuration.
    git("config", "filter.reviewtest.smudge", "sed s/hello/HELLO/g")
    git("config", "filter.reviewtest.clean", "cat")
    git("config", "filter.reviewtest.required", "true")

    # Reproduce the original failure with actual Git, not a mocked patcher.
    legacy = home / "legacy-worktree"
    git("worktree", "add", "--detach", str(legacy), base)
    patch = git("diff", "--binary", base, target).stdout.encode()
    legacy_result = subprocess.run(
        ["git", "apply", "--index"], cwd=legacy, env=env, input=patch,
        capture_output=True,
    )
    assert legacy_result.returncode != 0
    assert b"does not match index" in legacy_result.stderr
    git("worktree", "remove", "--force", str(legacy))

    review = review_path(git("review", target))
    assert_review(
        source, home, git, review, base,
        {"filtered.txt": b"HELLO new\n", "crlf.txt": b"after\r\n"},
    )
    assert git("status", "--porcelain").stdout == ""
    assert_cleanup(source, git, review)


def test_merge_commit_review_compares_first_parent(sandbox):
    source, home, env, git = sandbox
    (source / "base.txt").write_text("base\n")
    commit(git, "base")
    git("checkout", "-q", "-b", "feature")
    (source / "feature.txt").write_text("feature\n")
    commit(git, "feature")
    git("checkout", "-q", "main")
    (source / "main.txt").write_text("main\n")
    parent = commit(git, "main advance")
    git("merge", "--no-ff", "-m", "merge feature", "feature")
    merge = git("rev-parse", "HEAD").stdout.strip()

    review = review_path(git("review", merge))
    assert_review(
        source, home, git, review, parent,
        {"feature.txt": b"feature\n", "main.txt": b"main\n"},
    )
    assert_cleanup(source, git, review)


def test_diverged_range_uses_merge_base(sandbox):
    source, home, env, git = sandbox
    (source / "common.txt").write_text("common\n")
    base = commit(git, "common")
    git("checkout", "-q", "-b", "feature")
    (source / "feature.txt").write_text("feature\n")
    tip = commit(git, "feature")
    git("checkout", "-q", "main")
    (source / "main-only.txt").write_text("main\n")
    commit(git, "advance main")
    review = review_path(git("review-range", "main", tip))
    assert_review(
        source, home, git, review, base,
        {"feature.txt": b"feature\n", "main-only.txt": None},
    )
    assert_cleanup(source, git, review)


def test_launcher_failure_cleans_up_worktree(sandbox):
    source, home, env, git = sandbox
    (source / "file.txt").write_text("first\n")
    commit(git, "base")
    (source / "file.txt").write_text("second\n")
    commit(git, "target")
    result = git("review", "HEAD", check=False, env_override={"REVIEW_CODE_EXIT": "4"})
    assert result.returncode != 0
    assert len(git("worktree", "list").stdout.strip().splitlines()) == 1
    review_root = home / ".local/share/git-review"
    assert not list(review_root.glob("*/review-*"))
    assert not list(review_root.glob("*/workspaces/review-*"))


def test_unreview_refuses_to_guess_when_multiple_reviews_exist(sandbox):
    source, home, env, git = sandbox
    (source / "file.txt").write_text("first\n")
    base = commit(git, "base")
    (source / "file.txt").write_text("second\n")
    commit(git, "target")
    first = review_path(git("review", "HEAD"))
    second = review_path(git("review-range", base))
    result = git("unreview", check=False)
    assert result.returncode != 0
    assert "Multiple review worktrees" in result.stderr
    assert first.is_dir() and second.is_dir()
    assert (first.parent / "workspaces" / first.name).is_dir()
    assert (second.parent / "workspaces" / second.name).is_dir()
    git("unreview", cwd=first)
    assert not (first.parent / "workspaces" / first.name).exists()
    assert (second.parent / "workspaces" / second.name).is_dir()
    git("unreview", cwd=second)
    assert len(git("worktree", "list").stdout.strip().splitlines()) == 1


def test_review_from_linked_worktree_uses_repository_name(sandbox):
    """The title identifies the repository, not a developer's linked worktree."""
    source, home, env, git = sandbox
    (source / "a.txt").write_text("base\n")
    commit(git, "base")
    (source / "a.txt").write_text("new\n")
    target = commit(git, "target")
    linked = source.parent / "DCP-9612-feature-worktree"
    git("worktree", "add", "-b", "feature", str(linked), target)
    try:
        review = review_path(git("review", target, cwd=linked))
        ws = review.parent / "workspaces" / review.name / f"{source.name} · review · {target[:7]}.code-workspace"
        assert ws.is_file(), "Workspace title must use stable repository name"
        assert not (review.parent / "workspaces" / review.name / f"{linked.name} · review · {target[:7]}.code-workspace").exists()
        assert json.loads(ws.read_text())["folders"][0]["path"] == str(review)
        git("unreview", cwd=review)
        assert not ws.exists()
        assert git("rev-parse", "HEAD", cwd=linked).stdout.strip() == target
    finally:
        git("worktree", "remove", str(linked))


def test_long_utf8_repository_name_never_exceeds_filesystem_limits(sandbox):
    """Valid 200+ byte repository names must not break workspace creation."""
    source, home, env, git = sandbox
    long_name = "project-" + "ü" * 112
    long_repo = source.parent / long_name
    long_repo.mkdir()
    git("init", "-q", cwd=long_repo)
    git("config", "user.name", "Review Test", cwd=long_repo)
    git("config", "user.email", "review@example.invalid", cwd=long_repo)
    git("config", "commit.gpgsign", "false", cwd=long_repo)
    (long_repo / "a.txt").write_text("base\n")
    git("add", "-A", cwd=long_repo)
    git("commit", "-m", "base", "-q", cwd=long_repo)
    (long_repo / "a.txt").write_text("target\n")
    git("add", "-A", cwd=long_repo)
    git("commit", "-m", "target", "-q", cwd=long_repo)
    review = review_path(git("review", "HEAD", cwd=long_repo))
    directory = review.parent / "workspaces" / review.name
    workspace_files = list(directory.glob("*.code-workspace"))
    assert len(workspace_files) == 1
    assert len(workspace_files[0].name.encode("utf-8")) <= 255
    assert len(review.parent.name.encode("utf-8")) <= 255
    assert workspace_files[0].name.endswith(".code-workspace")
    assert git("status", "--porcelain", cwd=long_repo).stdout == ""
    git("unreview", cwd=review)
    assert not review.exists()
    assert not directory.exists()


def test_failed_workspace_cleanup_keeps_registered_review_recoverable(sandbox):
    """Never unregister a review before successfully removing its workspace."""
    source, home, env, git = sandbox
    (source / "a.txt").write_text("old\n")
    commit(git, "base")
    (source / "a.txt").write_text("new\n")
    commit(git, "target")
    review = review_path(git("review", "HEAD"))
    workspace_parent = review.parent / "workspaces"
    workspace_dir = workspace_parent / review.name
    assert workspace_dir.is_dir()
    workspace_parent.chmod(0o500)
    try:
        result = git("unreview", cwd=review, check=False)
        assert result.returncode != 0, "Workspace cleanup failure must be observable"
        assert review.exists(), "Registered review must survive failed cleanup"
        assert str(review) in git("worktree", "list").stdout
    finally:
        workspace_parent.chmod(0o700)
    git("unreview", cwd=review)
    assert not workspace_dir.exists()
    assert not review.exists()
    assert git("status", "--porcelain").stdout == ""
