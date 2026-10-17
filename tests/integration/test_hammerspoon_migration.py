"""Hammerspoon migration accepts arbitrary existing layouts in disposable homes."""

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "home/run_once_before_05-migrate-hammerspoon.sh"


def migrate(home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(MIGRATION)],
        env={**os.environ, "HOME": str(home)},
        text=True, capture_output=True,
    )


def backups(home: Path) -> list[Path]:
    parent = home / "Library/Application Support/dotfiles/backups"
    return list(parent.iterdir()) if parent.exists() else []


def test_migration_preserves_arbitrarily_linked_scripts_and_unmanaged_files(tmp_path):
    home = tmp_path / "home"
    root = home / ".hammerspoon"
    root.mkdir(parents=True)
    (root / "Spoons").mkdir()
    (root / "Spoons/custom.lua").write_text("keep")

    # No assumed source layout: all three targets are chosen by the Mac owner.
    legacy = home / "Projects/my-hammerspoon"
    (legacy / "modules").mkdir(parents=True)
    (legacy / "bin").mkdir()
    (legacy / "init.lua").write_text("personal init")
    (legacy / "modules/custom.lua").write_text("personal module")
    (legacy / "bin/tool").write_text("personal executable")
    (root / "init.lua").symlink_to(legacy / "init.lua")
    (root / "modules").symlink_to(legacy / "modules", target_is_directory=True)
    (root / "bin").symlink_to(legacy / "bin", target_is_directory=True)

    result = migrate(home)

    assert result.returncode == 0, result.stderr
    assert not any((root / entry).is_symlink() for entry in ("init.lua", "modules", "bin"))
    assert (root / "Spoons/custom.lua").read_text() == "keep"
    assert (legacy / "modules/custom.lua").read_text() == "personal module"
    assert len(backups(home)) == 1
    backup = backups(home)[0]
    assert (backup / "hammerspoon/init.lua").is_symlink()
    assert (backup / "resolved/init.lua").read_text() == "personal init"
    assert (backup / "resolved/modules/custom.lua").read_text() == "personal module"
    assert (backup / "resolved/bin/tool").read_text() == "personal executable"

    again = migrate(home)

    assert again.returncode == 0, again.stderr
    assert len(backups(home)) == 1


def test_migration_backs_up_existing_regular_files_without_removing_custom_scripts(tmp_path):
    home = tmp_path / "home"
    root = home / ".hammerspoon"
    (root / "modules").mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "init.lua").write_text("handwritten init")
    (root / "modules/custom.lua").write_text("handwritten module")
    (root / "bin/custom").write_text("handwritten executable")
    (root / "additional.lua").write_text("unmanaged file")

    result = migrate(home)

    assert result.returncode == 0, result.stderr
    assert (root / "init.lua").read_text() == "handwritten init"
    assert (root / "modules/custom.lua").read_text() == "handwritten module"
    assert (root / "bin/custom").read_text() == "handwritten executable"
    assert (root / "additional.lua").read_text() == "unmanaged file"
    backup = backups(home)[0]
    assert (backup / "hammerspoon/init.lua").read_text() == "handwritten init"
    assert (backup / "hammerspoon/modules/custom.lua").read_text() == "handwritten module"


def test_migration_detaches_symlinked_root_without_touching_original_checkout(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    original = home / "Repositories/custom-dotfiles/hammerspoon"
    original.mkdir(parents=True)
    (original / "init.lua").write_text("original")
    (original / "Spoons").mkdir()
    (original / "Spoons/keep.lua").write_text("custom spoon")
    root = home / ".hammerspoon"
    root.symlink_to(original, target_is_directory=True)

    result = migrate(home)

    assert result.returncode == 0, result.stderr
    assert root.is_dir() and not root.is_symlink()
    assert (root / "init.lua").read_text() == "original"
    assert (root / "Spoons/keep.lua").read_text() == "custom spoon"
    assert (original / "init.lua").read_text() == "original"
    backup = backups(home)[0]
    assert (backup / "original-root-link").is_symlink()
    assert (backup / "hammerspoon/init.lua").read_text() == "original"


def test_migration_refuses_broken_root_symlink_without_mutation(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    root = home / ".hammerspoon"
    root.symlink_to(home / "deleted-directory", target_is_directory=True)

    result = migrate(home)

    assert result.returncode != 0
    assert "not an accessible directory" in result.stderr
    assert root.is_symlink()
    assert not backups(home)


def test_migration_preserves_dangling_config_links_before_replacing_them(tmp_path):
    home = tmp_path / "home"
    root = home / ".hammerspoon"
    root.mkdir(parents=True)
    (root / "init.lua").symlink_to(home / "no-longer-here.lua")
    (root / "modules").symlink_to(home / "missing-modules", target_is_directory=True)

    result = migrate(home)

    assert result.returncode == 0, result.stderr
    assert not (root / "init.lua").is_symlink()
    assert not (root / "modules").is_symlink()
    backup = backups(home)[0]
    assert (backup / "hammerspoon/init.lua").is_symlink()
    assert (backup / "hammerspoon/modules").is_symlink()


def test_failed_backup_does_not_modify_any_existing_link(tmp_path):
    home = tmp_path / "home"
    root = home / ".hammerspoon"
    root.mkdir(parents=True)
    old = home / "my-init.lua"
    old.write_text("original init")
    (root / "init.lua").symlink_to(old)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_cp = fake_bin / "cp"
    fake_cp.write_text("#!/bin/sh\nexit 12\n")
    fake_cp.chmod(0o755)

    result = subprocess.run(
        ["/bin/bash", str(MIGRATION)],
        env={**os.environ, "HOME": str(home),
             "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        text=True, capture_output=True,
    )

    assert result.returncode != 0
    assert (root / "init.lua").is_symlink()
    assert old.read_text() == "original init"
    assert not (home / ".cache/chezmoi/hammerspoon-migration-complete").exists()


def test_migration_refuses_symlink_into_backup_ancestor(tmp_path):
    home = tmp_path / "home"
    root = home / ".hammerspoon"
    root.mkdir(parents=True)
    (root / "modules").symlink_to(home, target_is_directory=True)

    result = migrate(home)

    assert result.returncode != 0
    assert "contains the backup directory" in result.stderr
    assert (root / "modules").is_symlink()
    assert not backups(home)


def test_linked_config_upgrades_to_managed_files_in_isolated_home(
    tmp_path, profile_factory,
):
    rendered = profile_factory.render("personal")
    home = tmp_path / "home"
    root = home / ".hammerspoon"
    root.mkdir(parents=True)
    (root / "Spoons").mkdir()
    (root / "Spoons/keep.txt").write_text("unmanaged")
    old = home / ".config/hammerspoon-old"
    (old / "modules").mkdir(parents=True)
    (old / "bin").mkdir()
    (old / "init.lua").write_text("old init")
    (old / "modules/core.lua").write_text("old module")
    (root / "init.lua").symlink_to(old / "init.lua")
    (root / "modules").symlink_to(old / "modules", target_is_directory=True)
    (root / "bin").symlink_to(old / "bin", target_is_directory=True)
    env = {**os.environ, "HOME": str(home)}

    migration = migrate(home)
    assert migration.returncode == 0, migration.stderr
    command = [
        "chezmoi", "--source", str(ROOT / "home"),
        "--config", str(rendered.config), "--destination", str(home),
        "apply", "--exclude", "scripts",
    ]

    first = subprocess.run(command, env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    assert (root / "init.lua").is_file() and not (root / "init.lua").is_symlink()
    assert (root / "modules/core.lua").is_file()
    assert (root / "modules/audio_check.lua").is_file()
    assert os.access(root / "bin/mic_level", os.X_OK)
    assert (root / "Spoons/keep.txt").read_text() == "unmanaged"
    second = subprocess.run(command, env=env, capture_output=True, text=True)
    assert second.returncode == 0, second.stdout + second.stderr
    assert (root / "Spoons/keep.txt").read_text() == "unmanaged"
