"""Contract tests for local Raycast navigation and onboarding (no live GUI)."""

from pathlib import Path
import os
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "home/dot_config/raycast/scripts"
HOOK = ROOT / "home/run_after_60-raycast-onboarding.sh"

CONFIG_COMMANDS = {
    "open-codex-agents": ".codex/AGENTS.md",
    "open-codex-config": ".codex/config.toml",
    "open-zsh-config": ".zshrc",
    "open-aws-config": ".aws/config",
    "open-databricks-config": ".databrickscfg",
}


def fake_executable(folder: Path, name: str, script: str) -> None:
    path = folder / name
    path.write_text("#!/bin/sh\n" + script)
    path.chmod(0o755)


@pytest.mark.parametrize(("command", "relative_path"), CONFIG_COMMANDS.items())
def test_script_command_opens_exact_existing_file(command, relative_path, tmp_path):
    # Arrange: no Raycast dependency, capture invocation of the macOS opener.
    home = tmp_path / "home with spaces"
    home.mkdir()
    target = home / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("test content\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture = tmp_path / "open.txt"
    fake_executable(bin_dir, "open", 'printf "%s\\n" "$@" >> "$CAPTURE"\n')
    script = SCRIPTS / f"executable_{command}.sh"
    text = script.read_text()
    assert "# @raycast.schemaVersion 1" in text
    assert "# @raycast.title " in text
    assert "# @raycast.mode silent" in text

    # Act
    result = subprocess.run(
        ["bash", str(script)],
        env={**os.environ, "HOME": str(home),
             "PATH": f"{bin_dir}:{os.environ['PATH']}", "CAPTURE": str(capture)},
        capture_output=True, text=True,
    )

    # Assert: explicit VS Code application and exact quoted file path.
    assert result.returncode == 0, result.stderr
    assert capture.read_text().splitlines() == ["-a", "Visual Studio Code", str(target)]


@pytest.mark.parametrize(("command", "relative_path"), CONFIG_COMMANDS.items())
def test_script_command_never_creates_missing_config(command, relative_path, tmp_path):
    home = tmp_path / "empty-home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture = tmp_path / "open.txt"
    fake_executable(bin_dir, "open", 'printf "opened\\n" >> "$CAPTURE"\n')
    target = home / relative_path

    result = subprocess.run(
        ["bash", str(SCRIPTS / f"executable_{command}.sh")],
        env={**os.environ, "HOME": str(home),
             "PATH": f"{bin_dir}:{os.environ['PATH']}", "CAPTURE": str(capture)},
        capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert "File not found" in result.stderr
    assert not target.exists()
    assert not capture.exists()


def onboarding_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    home = tmp_path / "home"
    home.mkdir()
    (home / "Applications/Raycast.app").mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_executable(bin_dir, "uname", 'printf "Darwin\\n"\n')
    capture = tmp_path / "opened-url"
    fake_executable(bin_dir, "open", 'printf "%s\\n" "$@" >> "$CAPTURE"\n')
    return {
        **os.environ, "HOME": str(home), "CAPTURE": str(capture),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }, home, capture


def test_store_prompt_runs_once_per_machine(tmp_path):
    env, home, capture = onboarding_env(tmp_path)
    marker = home / ".cache/chezmoi/raycast-repository-manager-store-opened"

    first = subprocess.run(["sh", str(HOOK)], env=env, capture_output=True, text=True)
    second = subprocess.run(["sh", str(HOOK)], env=env, capture_output=True, text=True)

    assert first.returncode == second.returncode == 0
    assert capture.read_text().splitlines() == [
        "https://www.raycast.com/francesco_mecchi/repository-manager"
    ]
    assert marker.exists()
    assert "confirm Repository Manager installation" in first.stdout


def test_store_prompt_defers_when_optional_apps_skipped(tmp_path):
    env, home, capture = onboarding_env(tmp_path)
    env["DOTFILES_SKIP_OPTIONAL_APPS"] = "1"

    skipped = subprocess.run(["sh", str(HOOK)], env=env, capture_output=True, text=True)

    assert skipped.returncode == 0
    assert not capture.exists()
    assert not (home / ".cache/chezmoi/raycast-repository-manager-store-opened").exists()
    env.pop("DOTFILES_SKIP_OPTIONAL_APPS")
    assert subprocess.run(["sh", str(HOOK)], env=env, capture_output=True).returncode == 0
    assert capture.exists()


def test_failed_store_open_can_be_retried(tmp_path):
    env, home, capture = onboarding_env(tmp_path)
    bin_dir = tmp_path / "bin"
    fake_executable(bin_dir, "open", "exit 22\n")

    result = subprocess.run(["sh", str(HOOK)], env=env, capture_output=True, text=True)

    assert result.returncode == 22
    assert not (home / ".cache/chezmoi/raycast-repository-manager-store-opened").exists()
    assert not capture.exists()
