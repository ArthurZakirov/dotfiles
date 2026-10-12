"""Exercise the shared aliases against disposable Git repositories."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("from_source", [False, True])
@pytest.mark.parametrize("review_mode", ["commit", "range"])
def test_unreview_without_active_editor(tmp_path, from_source, review_mode):
    source = tmp_path / 'source'
    source.mkdir()
    env = {**os.environ, 'HOME': str(tmp_path), 'GIT_CONFIG_GLOBAL': os.devnull,
           'GIT_CONFIG_NOSYSTEM': '1'}
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    code = bin_dir / 'code'
    code.write_text('#!/bin/sh\nprintf \'%s\\n\' \"$2\" >> \"$HOME/opened-folders\"\n')
    code.chmod(0o755)
    helper = bin_dir / 'git-review-worktree'
    helper.write_bytes((ROOT / 'home/dot_local/bin/executable_git-review-worktree').read_bytes())
    helper.chmod(0o755)
    env['PATH'] = str(bin_dir) + os.pathsep + env['PATH']

    def git(*args, cwd=source):
        return subprocess.run(['git', *args], cwd=cwd, env=env,
                              check=True, text=True, capture_output=True).stdout.strip()

    git('init')
    git('config', 'user.name', 'Test')
    git('config', 'user.email', 'test@example.invalid')
    git('config', 'include.path', str(ROOT / 'home/dot_gitconfig'))
    (source / 'nested').mkdir()
    file = source / 'nested/file.txt'
    file.write_text('before\n')
    git('add', '.')
    git('commit', '-m', 'base')
    file.write_text('after\n')
    git('commit', '-am', 'target')
    file.write_text('uncommitted source edit\n')
    source_status = git('status', '--porcelain')
    source_head = git('rev-parse', 'HEAD')
    review_output = git('review', 'HEAD') if review_mode == 'commit' else git('review-range', 'HEAD^')
    review = Path(review_output.splitlines()[-1])
    assert (review / 'nested/file.txt').read_text() == 'after\n'
    # Exercise both the review checkout and the original workspace folder.
    task_cwd = source if from_source else review / 'nested'
    result = subprocess.run(['git', 'unreview'], cwd=task_cwd,
                            env=env, check=True, capture_output=True, text=True)
    assert result.stdout.strip() == str(source)
    assert not review.exists()
    opened = (tmp_path / 'opened-folders').read_text().splitlines()
    expected_title = f"{source.name} · review · {source_head[:7]}.code-workspace"
    assert len(opened) == 2
    assert Path(opened[0]).name == expected_title
    assert Path(opened[0]).parent == review.parent / "workspaces" / review.name
    assert not Path(opened[0]).parent.exists()
    assert opened[1] == str(source)
    assert file.read_text() == 'uncommitted source edit\n'
    assert git('status', '--porcelain') == source_status
    assert git('rev-parse', 'HEAD') == source_head


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_chezmoi_manages_review_files(profile, profile_factory):
    rendered = profile_factory.render(profile)
    for target, source in (
        (".gitconfig", "home/dot_gitconfig"),
        (".local/bin/git-review-worktree", "home/dot_local/bin/executable_git-review-worktree"),
    ):
        assert profile_factory.chezmoi(
            rendered.config, "cat", str(Path.home() / target)
        ) == (ROOT / source).read_text()


def test_local_git_config_overrides_shared_config(tmp_path):
    managed_config = tmp_path / ".gitconfig"
    managed_config.write_text((ROOT / "home/dot_gitconfig").read_text())
    (tmp_path / ".gitconfig.local").write_text(
        "[user]\n\tname = Local User\n\temail = local@example.invalid\n"
    )
    environment = {
        **os.environ,
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": str(managed_config),
        "GIT_CONFIG_NOSYSTEM": "1",
    }

    def git(*args):
        return subprocess.run(
            ["git", "config", "--includes", "--global", *args], env=environment,
            check=True, text=True, capture_output=True,
        ).stdout.strip()

    assert git("user.name") == "Local User"
    assert git("user.email") == "local@example.invalid"
    assert git("alias.review") == "!git-review-worktree commit"


def test_migration_preserves_existing_git_config_as_local_override(tmp_path):
    existing_config = tmp_path / ".gitconfig"
    existing_config.write_text("[user]\n\temail = local@example.invalid\n")
    environment = {**os.environ, "HOME": str(tmp_path)}

    subprocess.run(
        ["sh", str(ROOT / "home/run_once_before_15-migrate-git-config.sh")],
        env=environment, check=True,
    )

    assert not existing_config.exists()
    assert (tmp_path / ".gitconfig.local").read_text() == (
        "[user]\n\temail = local@example.invalid\n"
    )


def test_migration_creates_empty_local_config_for_new_machine(tmp_path):
    subprocess.run(
        ["sh", str(ROOT / "home/run_once_before_15-migrate-git-config.sh")],
        env={**os.environ, "HOME": str(tmp_path)}, check=True,
    )

    assert (tmp_path / ".gitconfig.local").read_text() == ""


def test_review_rejects_root_commit_with_clear_message(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    environment = {
        **os.environ,
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    helper = bin_dir / "git-review-worktree"
    helper.write_bytes(
        (ROOT / "home/dot_local/bin/executable_git-review-worktree").read_bytes()
    )
    helper.chmod(0o755)
    environment["PATH"] = f"{bin_dir}{os.pathsep}{environment['PATH']}"

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=source, env=environment,
            text=True, capture_output=True,
        )

    assert git("init").returncode == 0
    assert git("config", "user.name", "Test").returncode == 0
    assert git("config", "user.email", "test@example.invalid").returncode == 0
    assert git("config", "include.path", str(ROOT / "home/dot_gitconfig")).returncode == 0
    (source / "file.txt").write_text("root\n")
    assert git("add", "file.txt").returncode == 0
    assert git("commit", "-m", "root").returncode == 0

    result = git("review", "HEAD")

    assert result.returncode != 0
    assert "Cannot review a root commit" in result.stderr


def test_review_range_initializes_remote_default_branch(tmp_path):
    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    source.mkdir()
    environment = {
        **os.environ,
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    helper = bin_dir / "git-review-worktree"
    helper.write_bytes(
        (ROOT / "home/dot_local/bin/executable_git-review-worktree").read_bytes()
    )
    helper.chmod(0o755)
    environment["PATH"] = f"{bin_dir}{os.pathsep}{environment['PATH']}"

    def git(*args, cwd=source):
        return subprocess.run(
            ["git", *args], cwd=cwd, env=environment, check=True,
            text=True, capture_output=True,
        ).stdout.strip()

    git("init")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    git("config", "include.path", str(ROOT / "home/dot_gitconfig"))
    (source / "file.txt").write_text("base\n")
    git("add", "file.txt")
    git("commit", "-m", "base")
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(
        ["git", "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main"],
        check=True,
    )
    git("remote", "add", "origin", str(remote))
    git("push", "origin", "HEAD:main")
    (source / "file.txt").write_text("target\n")
    git("commit", "-am", "target")

    assert subprocess.run(
        ["git", "symbolic-ref", "-q", "refs/remotes/origin/HEAD"],
        cwd=source, env=environment,
    ).returncode != 0
    review = Path(git("review-range").splitlines()[-1])
    assert (review / "file.txt").read_text() == "target\n"
    subprocess.run(["git", "unreview"], cwd=source, env=environment, check=True)
