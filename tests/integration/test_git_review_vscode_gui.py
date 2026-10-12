"""End-to-end check of the real VS Code Git extension, not a launcher stub.

Opt in via RUN_VSCODE_GUI_E2E=1. CI runs it under Xvfb; macOS developers can
run it with their real VS Code installation. Profiles are always isolated.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "home/dot_local/bin/executable_git-review-worktree"
GITCONFIG = ROOT / "home/dot_gitconfig"

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_VSCODE_GUI_E2E") != "1",
    reason="Requires an actual GUI VS Code installation; set RUN_VSCODE_GUI_E2E=1",
)


def wait_for_git_scan(profile: Path, expected_repo: Path, timeout: float = 65) -> str:
    """Require the real Git extension to open only the expected worktree."""
    end = time.monotonic() + timeout
    latest = ""
    while time.monotonic() < end:
        logs = sorted(profile.glob("logs/**/vscode.git/Git.log"))
        latest = "\n".join(p.read_text(errors="replace") for p in logs)
        opened = re.findall(r"\[Model\]\[openRepository\] Opened repository \(path\): (.+)", latest)
        scans = re.findall(
            r"Initial repository scan completed - repositories \((\d+)\), "
            r"closed repositories \((\d+)\), parent repositories \((\d+)\)",
            latest,
        )
        if opened and scans:
            assert all(Path(p).resolve() == expected_repo.resolve() for p in opened), (
                f"Unexpected repositories: {opened}\n{latest[-5000:]}"
            )
            assert all(n == "1" and closed == "0" and parent == "0" for n, closed, parent in scans), (
                f"VS Code detected multiple or parent repositories: {scans}\n{latest[-5000:]}"
            )
            return latest
        time.sleep(0.5)
    raise AssertionError(f"VS Code did not complete its Git scan in {timeout}s:\n{latest[-6000:]}")


def stop_isolated_vscode(profile: Path) -> None:
    """Terminate only processes belonging to the disposable VS Code profile."""
    result = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=True)
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        pid, cmd = parts
        if (
            str(profile) in cmd
            and ("Visual Studio Code.app" in cmd or "/code" in cmd or "/Code" in cmd)
            and int(pid) != os.getpid()
        ):
            try:
                os.kill(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass


def test_real_vscode_git_extension_sees_single_review_repository(tmp_path):
    """Exercise Git alias → Python helper → real VS Code → Git extension."""
    real_code = shutil.which("code")
    assert real_code is not None, "Install VS Code and expose its code CLI"

    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_bytes(GITCONFIG.read_bytes())
    (home / ".gitconfig.local").write_text("")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    helperdir = home / ".local/bin"
    helperdir.mkdir(parents=True)
    helper = helperdir / "git-review-worktree"
    shutil.copy2(HELPER, helper)
    helper.chmod(0o755)

    profile = tmp_path / "vscode-profile"
    settings = profile / "User/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        '{"workbench.startupEditor":"none","git.autofetch":false,'
        '"git.detectWorktrees":true,"git.autoRepositoryDetection":true,'
        '"window.restoreWindows":"none","telemetry.telemetryLevel":"off"}\n'
    )
    extensions = tmp_path / "vscode-extensions"
    extensions.mkdir()
    # Only modify this private wrapper, NEVER the user's installed VS Code CLI.
    code = bindir / "code"
    code.write_text(
        "#!/bin/sh\n"
        f'exec "{real_code}" --disable-extensions --disable-gpu '
        f'--disable-workspace-trust --user-data-dir "{profile}" '
        f'--extensions-dir "{extensions}" "$@"\n'
    )
    code.chmod(0o755)

    env = {
        **{k: v for k, v in os.environ.items() if k not in (
            "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_PREFIX", "GIT_CONFIG_PARAMETERS", "GIT_CEILING_DIRECTORIES",
        )},
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "PATH": f"{bindir}{os.pathsep}{helperdir}{os.pathsep}{os.environ['PATH']}",
    }
    source = tmp_path / "provisioning"
    source.mkdir()

    def git(*args, cwd=None, overrides=None, check=True):
        return subprocess.run(
            ["git", *args], cwd=cwd or source,
            env={**env, **(overrides or {})}, check=check, capture_output=True, text=True,
        )

    review = None
    try:
        git("init", "-q")
        git("config", "user.name", "Review GUI Test")
        git("config", "user.email", "review@example.invalid")
        git("config", "commit.gpgsign", "false")
        for name in (".vscode", "events", "konux", "predeploy", "tests"):
            folder = source / name
            folder.mkdir()
            (folder / "file.txt").write_text("before\n")
        git("add", "-A")
        git("commit", "-m", "base", "-q")
        base = git("rev-parse", "HEAD").stdout.strip()
        for name in (".vscode", "events", "konux", "predeploy", "tests"):
            (source / name / "file.txt").write_text("after\n")
        git("add", "-A")
        git("commit", "-m", "target", "-q")
        target = git("rev-parse", "HEAD").stdout.strip()

        # Preserve source edits, and deliberately inject the variables that
        # previously caused VS Code to show the source branch in every folder.
        (source / "scratch.txt").write_text("irreplaceable work\n")
        before_status = git("status", "--porcelain").stdout
        result = git("review", target, overrides={
            "GIT_DIR": str(source / ".git"), "GIT_WORK_TREE": str(source),
            "GIT_INDEX_FILE": str(source / ".git/index"),
            "GIT_PREFIX": "konux/",
        })
        review = Path(result.stdout.splitlines()[-1])
        assert git("rev-parse", "HEAD", cwd=review).stdout.strip() == base
        assert git("status", "--porcelain").stdout == before_status

        log = wait_for_git_scan(profile, review)
        assert "[Model][openRepository] Opened repository (kind): worktree" in log
        assert "Initial repository scan completed - repositories (1)" in log

        # Return through the real alias. Source must remain untouched.
        git("unreview", cwd=review)
        assert not review.exists()
        assert git("status", "--porcelain").stdout == before_status
        assert (source / "scratch.txt").read_text() == "irreplaceable work\n"
        assert git("rev-parse", "HEAD").stdout.strip() == target
        assert len(git("worktree", "list", "--porcelain").stdout.split("worktree ")) == 2
    finally:
        stop_isolated_vscode(profile)
