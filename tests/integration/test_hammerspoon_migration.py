"""Legacy Hammerspoon symlink migration using disposable HOME directories."""

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "home/run_once_before_05-migrate-hammerspoon.sh"


def test_migration_backs_up_legacy_links_and_preserves_unmanaged_files(tmp_path):
    home = tmp_path / "home"
    config = home / ".hammerspoon"
    config.mkdir(parents=True)
    (config / "Spoons").mkdir()
    (config / "Spoons/custom.lua").write_text("keep")
    local = home / ".hammerspoon-local"
    local.mkdir()
    (local / "init.lua").write_text("legacy init")
    skill = home / ".agents/skills/hammerspoon-macos-setup/assets/hammerspoon"
    (skill / "modules").mkdir(parents=True)
    (skill / "modules/core.lua").write_text("legacy module")
    (config / "init.lua").symlink_to(local / "init.lua")
    (config / "modules").symlink_to(skill / "modules", target_is_directory=True)
    (config / "bin").symlink_to(skill / "bin", target_is_directory=True)

    env = {**os.environ, "HOME": str(home)}
    subprocess.run(["/bin/bash", str(MIGRATION)], env=env, check=True)
    assert (config / "Spoons/custom.lua").read_text() == "keep"
    assert not (config / "init.lua").is_symlink()
    assert not (config / "modules").is_symlink()
    assert not (config / "bin").is_symlink()
    backups = list((home / "Library/Application Support/dotfiles/backups").iterdir())
    assert len(backups) == 1
    assert (backups[0] / "hammerspoon/init.lua").is_symlink()
    assert (backups[0] / "resolved/init.lua").read_text() == "legacy init"
    assert (backups[0] / "resolved/modules/core.lua").read_text() == "legacy module"
    assert (backups[0] / "hammerspoon-local/init.lua").read_text() == "legacy init"

    # A second execution makes no further destructive changes.
    subprocess.run(["/bin/bash", str(MIGRATION)], env=env, check=True)
    assert (config / "Spoons/custom.lua").read_text() == "keep"


def test_migration_refuses_unknown_symlinks_without_modifying_them(tmp_path):
    home = tmp_path / "home"
    config = home / ".hammerspoon"
    config.mkdir(parents=True)
    (config / "init.lua").symlink_to("/some/other/user/config")
    result = subprocess.run(
        ["/bin/bash", str(MIGRATION)], env={**os.environ, "HOME": str(home)},
        text=True, capture_output=True,
    )
    assert result.returncode != 0
    assert "Refusing to replace" in result.stderr
    assert (config / "init.lua").is_symlink()
    assert not (home / "Library/Application Support/dotfiles/backups").exists()


def test_legacy_symlinks_upgrade_to_managed_files_in_isolated_home(
    tmp_path, profile_factory,
):
    rendered = profile_factory.render("personal")
    home = tmp_path / "home"
    directory = home / ".hammerspoon"
    directory.mkdir(parents=True)
    (directory / "Spoons").mkdir()
    (directory / "Spoons/keep.txt").write_text("unmanaged")
    local = home / ".hammerspoon-local"
    local.mkdir()
    (local / "init.lua").write_text("old init")
    skill = home / ".agents/skills/hammerspoon-macos-setup/assets/hammerspoon"
    (skill / "modules").mkdir(parents=True)
    (skill / "modules/core.lua").write_text("old module")
    (directory / "init.lua").symlink_to(local / "init.lua")
    (directory / "modules").symlink_to(skill / "modules", target_is_directory=True)
    (directory / "bin").symlink_to(skill / "bin", target_is_directory=True)
    env = {**os.environ, "HOME": str(home)}

    subprocess.run(["/bin/bash", str(MIGRATION)], env=env, check=True)
    command = [
        "chezmoi", "--source", str(ROOT / "home"),
        "--config", str(rendered.config), "--destination", str(home),
        "apply", "--exclude", "scripts", "--force",
    ]
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert (directory / "init.lua").is_file() and not (directory / "init.lua").is_symlink()
    assert (directory / "modules/core.lua").is_file()
    assert (directory / "modules/audio_check.lua").is_file()
    assert os.access(directory / "bin/mic_level", os.X_OK)
    assert (directory / "Spoons/keep.txt").read_text() == "unmanaged"
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert (directory / "Spoons/keep.txt").read_text() == "unmanaged"
