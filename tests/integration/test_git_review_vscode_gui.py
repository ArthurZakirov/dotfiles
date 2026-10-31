"""End-to-end check of the real VS Code Git extension, not a launcher stub.

Run only in an isolated CI runner with Xvfb. A separate VS Code profile on
a personal Mac is NOT a sufficient process or keychain isolation boundary.
"""

from __future__ import annotations

import json
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
    not (os.environ.get("RUN_VSCODE_GUI_E2E") == "1" and os.environ.get("CI") == "true"
         and os.name == "posix" and __import__("sys").platform.startswith("linux")),
    reason="Real VS Code GUI test is restricted to isolated Linux CI runners",
)


def wait_for_git_scan(profile: Path, expected_repo: Path, timeout: float = 65) -> str:
    """Require the real Git extension to open only the expected worktree."""
    end = time.monotonic() + timeout
    latest = ""
    settle_until = None
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
            # Repository discovery can continue after the initial scan.
            if settle_until is None:
                settle_until = time.monotonic() + 4
            if time.monotonic() >= settle_until:
                return latest
        time.sleep(0.5)
    raise AssertionError(f"VS Code did not finish a stable Git scan in {timeout}s:\n{latest[-6000:]}")


def wait_for_source_reopen(profile: Path, source: Path, timeout: float = 45) -> None:
    """Require a fresh Git extension open event for the original checkout."""
    end = time.monotonic() + timeout
    latest = ""
    while time.monotonic() < end:
        logs = sorted(profile.glob("logs/**/vscode.git/Git.log"))
        latest = "\n".join(p.read_text(errors="replace") for p in logs)
        opened = re.findall(r"\[Model\]\[openRepository\] Opened repository \(path\): (.+)", latest)
        if opened and Path(opened[-1]).resolve() == source.resolve():
            return
        time.sleep(0.5)
    raise AssertionError(
        f"VS Code did not return to original repository after unreview:\n{latest[-6000:]}"
    )


def vscode_pids(profile: Path) -> list[int]:
    """Find only VS Code processes using this test's unique temporary profile."""
    result = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=True)
    matches = []
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
            matches.append(int(pid))
    return matches


def stop_isolated_vscode(profile: Path) -> None:
    """Terminate only disposable CI profile processes; never operate on a Mac."""
    assert os.environ.get("CI") == "true" and __import__("sys").platform.startswith("linux")
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in vscode_pids(profile):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if not vscode_pids(profile):
                return
            time.sleep(0.2)
    assert not vscode_pids(profile), "Isolated VS Code processes were not terminated"


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
    # Check actual VS Code task invocation without resolving dependencies in CI.
    task_log = tmp_path / "pysetup-task.log"
    pysetup = helperdir / "pysetup"
    pysetup.write_text("#!/usr/bin/env python3\nimport os\nfrom pathlib import Path\nimport subprocess\nimport sys\nimport venv\nif sys.argv[1] == \"--prepare-interpreter\":\n    root = Path(sys.argv[2])\n    venv.EnvBuilder(with_pip=False).create(root / \".venv\")\n    git_path = subprocess.check_output(\n        [\"git\", \"rev-parse\", \"--git-path\", \"info/exclude\"], cwd=root, text=True\n    ).strip()\n    exclude = Path(git_path)\n    if not exclude.is_absolute():\n        exclude = root / exclude\n    with exclude.open(\"a\") as output:\n        output.write(\"\\n.venv/\\n\")\n    Path(os.environ[\"REVIEW_BOOTSTRAP_LOG\"]).write_text(str(root) + \"\\n\")\nelse:\n    Path(os.environ[\"REVIEW_TASK_LOG\"]).write_text(sys.argv[1] + \"\\n\")\n")
    pysetup.chmod(0o755)

    profile = tmp_path / "vscode-profile"
    settings = profile / "User/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        '{"workbench.startupEditor":"none","git.autofetch":false,'
        '"git.detectWorktrees":true,"git.autoRepositoryDetection":true,'
        '"window.restoreWindows":"none","telemetry.telemetryLevel":"off",'
        '"task.allowAutomaticTasks":"on","python.useEnvironmentsExtension":true}\n'
    )
    extensions = tmp_path / "vscode-extensions"
    extensions.mkdir()
    # Use the same real Microsoft backends implicated in the regression. The
    # user setting opts into the preview backend; the review must override it.
    subprocess.run([
        real_code, "--user-data-dir", str(profile), "--extensions-dir", str(extensions),
        "--install-extension", "ms-python.python@2026.10.0",
        "--install-extension", "ms-python.vscode-python-envs@1.40.0",
    ], check=True, capture_output=True, text=True, timeout=180)
    probe = extensions / "test.python-selection-0.0.1"
    probe.mkdir()
    (probe / "package.json").write_text(json.dumps({
        "name": "python-selection", "publisher": "test", "version": "0.0.1",
        "engines": {"vscode": "^1.100.0"}, "main": "./extension.js",
        "activationEvents": ["onStartupFinished"],
    }))
    shutil.copy2(ROOT / "tests/support/vscode_python_probe.js", probe / "extension.js")
    review_extension = ROOT / "home/dot_vscode/extensions/agentdesk.git-review-ui-0.1.0"
    shutil.copytree(review_extension, extensions / review_extension.name)
    # Only modify this private wrapper, NEVER the user's installed VS Code CLI.
    code = bindir / "code"
    code.write_text(
        "#!/bin/sh\n"
        f'exec "{real_code}" --disable-gpu '
        f'--disable-workspace-trust --user-data-dir "{profile}" '
        f'--extensionDevelopmentPath="{probe}" '
        f'--extensionDevelopmentPath="{extensions / review_extension.name}" '
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
        "REVIEW_TASK_LOG": str(task_log),
        "REVIEW_BOOTSTRAP_LOG": str(tmp_path / "pysetup-bootstrap.log"),
        "GIT_REVIEW_GUI_TEST_MARKER": str(tmp_path / "source-control-opened.log"),
        "GIT_REVIEW_DIFF_TEST_MARKER": str(tmp_path / "opened-diff-tabs.json"),
        "GIT_REVIEW_PYTHON_TEST_MARKER": str(tmp_path / "python-selection.json"),
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
        (source / "pyproject.toml").write_text(
            '[tool.poetry]\nname = "sample"\nversion = "0.1.0"\n'
        )
        (source / "poetry.lock").write_text("# test lockfile\n")
        (source / "deleted.txt").write_text("deleted before\n")
        git("add", "-A")
        git("commit", "-m", "base", "-q")
        base = git("rev-parse", "HEAD").stdout.strip()
        for name in (".vscode", "events", "konux", "predeploy", "tests"):
            (source / name / "file.txt").write_text("after\n")
        (source / "deleted.txt").unlink()
        (source / "added.txt").write_text("added after\n")
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

        assert (review / ".venv/bin/python").exists()
        assert Path(env["REVIEW_BOOTSTRAP_LOG"]).read_text().strip() == str(review)
        log = wait_for_git_scan(profile, review)
        assert "[Model][openRepository] Opened repository (kind): worktree" in log
        assert "Initial repository scan completed - repositories (1)" in log

        # Assert the editor really launches the generated folder-open task.
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not task_log.exists():
            time.sleep(0.5)
        assert task_log.exists(), "VS Code did not execute the folder-open task"
        assert task_log.read_text().strip() == str(review)

        python_marker = Path(env["GIT_REVIEW_PYTHON_TEST_MARKER"])
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and not python_marker.exists():
            time.sleep(0.5)
        if not python_marker.exists():
            stage = Path(str(python_marker) + ".stage")
            progress = stage.read_text() if stage.exists() else "probe never activated"
            logs = "\n".join(
                path.read_text(errors="replace")
                for path in sorted(profile.glob("logs/**/exthost.log"))
            )
            pytest.fail(f"Python probe stalled at {progress}:\n{logs[-6000:]}")
        selection = json.loads(python_marker.read_text())
        assert "error" not in selection, selection
        for phase in ("initial", "refreshed"):
            # Do not resolve symlinks: the venv executable points at global
            # Python, but invoking that global target loses the virtualenv.
            assert selection[phase]["executable"] == str(review / ".venv/bin/python"), selection
            assert selection[phase]["execCommand"] == [str(review / ".venv/bin/python")], selection
            prefix = subprocess.check_output([
                *selection[phase]["execCommand"], "-c", "import sys; print(sys.prefix)",
            ], text=True).strip()
            assert prefix == str(review / ".venv")

        # The real extension confirms that VS Code executed the SCM command.
        marker = Path(env["GIT_REVIEW_GUI_TEST_MARKER"])
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not marker.exists():
            time.sleep(0.5)
        assert marker.exists(), "Review UI extension did not acknowledge opening SCM"
        assert marker.read_text().strip() == "scm-opened"

        # Inspect actual VS Code TabInputTextDiff tabs and their document
        # content, not just commands dispatched by a stub.
        diff_marker = Path(env["GIT_REVIEW_DIFF_TEST_MARKER"])
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not diff_marker.exists():
            time.sleep(0.5)
        assert diff_marker.exists(), "VS Code did not open the review diff editors"
        diff_result = json.loads(diff_marker.read_text())
        assert diff_result["expected"] == 7
        tabs = diff_result["tabs"]
        assert len(tabs) == 7, tabs
        assert len({tab["modified"] for tab in tabs}) == 7
        assert all(not tab["preview"] for tab in tabs)
        modified = {tab["label"]: tab for tab in tabs}
        for name in (".vscode", "events", "konux", "predeploy", "tests"):
            tab = modified[f"{name}/file.txt"]
            assert tab["originalText"] == "before\n"
            assert tab["modifiedText"] == "after\n"
            assert tab["original"].startswith("git:")
            assert tab["modified"].startswith("file:")
        added = modified["added.txt"]
        assert added["originalText"] == ""
        assert added["modifiedText"] == "added after\n"
        assert added["original"].startswith("git-review-empty:")
        assert added["modified"].startswith("file:")
        deleted = modified["deleted.txt"]
        assert deleted["originalText"] == "deleted before\n"
        assert deleted["modifiedText"] == ""
        assert deleted["original"].startswith("git:")
        assert deleted["modified"].startswith("git-review-empty:")

        # Return through the real alias. Source must remain untouched.
        git("unreview", cwd=review)
        wait_for_source_reopen(profile, source)
        assert not review.exists()
        assert git("status", "--porcelain").stdout == before_status
        assert (source / "scratch.txt").read_text() == "irreplaceable work\n"
        assert git("rev-parse", "HEAD").stdout.strip() == target
        assert len(git("worktree", "list", "--porcelain").stdout.split("worktree ")) == 2
    finally:
        stop_isolated_vscode(profile)
        # The source is a throwaway repository created by this test. If any
        # assertion fails, leave neither a registered worktree nor a VS Code
        # process behind. Never touch an existing user repository.
        if review is not None and review.exists():
            # Only the throwaway source repository created above is eligible.
            if source.is_relative_to(tmp_path) and review.is_relative_to(home):
                git("worktree", "remove", "--force", str(review), check=False)
                shutil.rmtree(review.parent / "workspaces" / review.name, ignore_errors=True)
