"""Contract tests for local Raycast navigation and onboarding (no live GUI)."""

from pathlib import Path
import os
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "home/dot_config/raycast/scripts"
HOOK = ROOT / "home/run_after_60-raycast-onboarding.sh"
LAUNCHER = ROOT / "home/dot_config/raycast/lib/executable_open-target.sh"

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


def install_launcher(home: Path) -> None:
    """Install the real shared opener under a disposable HOME for wrapper tests."""
    installed = home / ".config/raycast/lib/open-target.sh"
    installed.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(LAUNCHER, installed)
    installed.chmod(0o755)


@pytest.mark.parametrize(("command", "relative_path"), CONFIG_COMMANDS.items())
def test_script_command_opens_exact_existing_file(command, relative_path, tmp_path):
    # Arrange: no Raycast dependency, capture invocation of the macOS opener.
    home = tmp_path / "home with spaces"
    home.mkdir()
    install_launcher(home)
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
    install_launcher(home)
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



# These names and targets come from the eight entries in the original local
# quicklinks.json. Keep their user-facing titles stable after migration.
LEGACY_QUICKLINKS = {
    "open-raycast-quicklinks": ("quicklinks.json", ".config/raycast/quicklinks.json", "file"),
    "open-local-bin": (".local/bin scripts", ".local/bin", "directory"),
    "open-zsh-config": (".zshrc", ".zshrc", "file"),
    "open-personal-repos": ("repos/personal", "Repos/personal", "directory"),
    "open-repos": ("repos", "Repos", "directory"),
    "open-codex-config": ("config.toml", ".codex/config.toml", "file"),
    "open-codex-directory": (".codex", ".codex", "directory"),
}
CHEZMOI_COMMAND = "executable_open-chezmoi-dotfiles.sh"


@pytest.mark.parametrize(
    ("command", "entry"), LEGACY_QUICKLINKS.items(),
    ids=LEGACY_QUICKLINKS,
)
def test_migrated_quicklink_opens_existing_target(command, entry, tmp_path):
    # Arrange: a fresh Mac with either a file or folder at the expected path.
    title, relative_path, kind = entry
    home = tmp_path / "home with spaces"
    home.mkdir()
    install_launcher(home)
    target = home / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind == "file":
        target.write_text("local config\n")
    else:
        target.mkdir()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture = tmp_path / "open.txt"
    fake_executable(bin_dir, "open", 'printf "%s\n" "$@" >> "$CAPTURE"\n')
    script = SCRIPTS / f"executable_{command}.sh"
    assert f"# @raycast.title {title}\n" in script.read_text()

    # Act
    result = subprocess.run(
        ["bash", str(script)],
        env={**os.environ, "HOME": str(home),
             "PATH": f"{bin_dir}:{os.environ['PATH']}", "CAPTURE": str(capture)},
        capture_output=True, text=True,
    )

    # Assert: files and folders both open in the same application as Quicklinks.
    assert result.returncode == 0, result.stderr
    assert capture.read_text().splitlines() == ["-a", "Visual Studio Code", str(target)]


@pytest.mark.parametrize(
    ("command", "entry"), LEGACY_QUICKLINKS.items(),
    ids=LEGACY_QUICKLINKS,
)
def test_migrated_quicklink_never_creates_missing_target(command, entry, tmp_path):
    _, relative_path, kind = entry
    home = tmp_path / "fresh-home"
    home.mkdir()
    install_launcher(home)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture = tmp_path / "open.txt"
    fake_executable(bin_dir, "open", 'printf "unexpected\n" >> "$CAPTURE"\n')
    target = home / relative_path

    result = subprocess.run(
        ["bash", str(SCRIPTS / f"executable_{command}.sh")],
        env={**os.environ, "HOME": str(home),
             "PATH": f"{bin_dir}:{os.environ['PATH']}", "CAPTURE": str(capture)},
        capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert ("File" if kind == "file" else "Directory") + " not found" in result.stderr
    assert not target.exists()
    assert not capture.exists()


def test_chezmoi_quicklink_finds_checkout_without_local_symlink(tmp_path):
    # Arrange: chezmoi's configured source can live anywhere on another Mac.
    repo = tmp_path / "another checkout with spaces"
    source = repo / "home"
    source.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    home = tmp_path / "home"
    home.mkdir()
    install_launcher(home)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture = tmp_path / "open.txt"
    fake_executable(bin_dir, "chezmoi", 'printf "%s\n" "$FAKE_CHEZMOI_SOURCE"\n')
    fake_executable(bin_dir, "open", 'printf "%s\n" "$@" >> "$CAPTURE"\n')
    script = SCRIPTS / CHEZMOI_COMMAND
    assert "# @raycast.title chezmoi dotfiles\n" in script.read_text()

    # Act
    result = subprocess.run(
        ["bash", str(script)],
        env={**os.environ, "HOME": str(home),
             "FAKE_CHEZMOI_SOURCE": str(source),
             "PATH": f"{bin_dir}:{os.environ['PATH']}", "CAPTURE": str(capture)},
        capture_output=True, text=True,
    )

    # Assert: open the Git root, not the chezmoi source subdirectory.
    assert result.returncode == 0, result.stderr
    assert capture.read_text().splitlines() == ["-a", "Visual Studio Code", str(repo)]
    assert not (home / ".local/share/chezmoi").exists()


def test_chezmoi_quicklink_rejects_non_git_source(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    install_launcher(home)
    source = tmp_path / "not-a-repository"
    source.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture = tmp_path / "open.txt"
    fake_executable(bin_dir, "chezmoi", 'printf "%s\n" "$FAKE_CHEZMOI_SOURCE"\n')
    fake_executable(bin_dir, "open", 'printf "unexpected\n" >> "$CAPTURE"\n')

    result = subprocess.run(
        ["bash", str(SCRIPTS / CHEZMOI_COMMAND)],
        env={**os.environ, "HOME": str(home),
             "FAKE_CHEZMOI_SOURCE": str(source),
             "PATH": f"{bin_dir}:{os.environ['PATH']}", "CAPTURE": str(capture)},
        capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert not capture.exists()


def test_script_directory_contains_all_eight_quicklinks_plus_three_extras():
    expected = {
        *(f"executable_{name}.sh" for name in LEGACY_QUICKLINKS),
        CHEZMOI_COMMAND,
        "executable_open-codex-agents.sh",
        "executable_open-aws-config.sh",
        "executable_open-databricks-config.sh",
    }
    assert {file.name for file in SCRIPTS.glob("*.sh")} == expected


def test_feature_guide_lists_every_managed_quicklink():
    guide = (ROOT / "docs/features/raycast.md").read_text()
    titles = (entry[0] for entry in LEGACY_QUICKLINKS.values())
    for title in (*titles, "chezmoi dotfiles"):
        assert f"| `{title}` |" in guide


def test_launcher_rejects_invalid_type(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    install_launcher(home)
    result = subprocess.run(
        ["bash", str(LAUNCHER), "unsupported", "/some/path"],
        env={**os.environ, "HOME": str(home)},
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "Unknown target type" in result.stderr


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
