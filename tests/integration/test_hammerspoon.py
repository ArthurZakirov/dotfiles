"""Hammerspoon profile rendering and safe migration on disposable HOME trees."""

from pathlib import Path
import os
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "home/run_once_before_05-migrate-hammerspoon.sh"
METER = ROOT / "home/dot_hammerspoon/bin/executable_mic_level"


@pytest.mark.parametrize("profile", ("personal", "professional"))
def test_managed_hammerspoon_is_standalone_and_profile_scoped(profile, profile_factory):
    rendered = profile_factory.render(profile)
    managed = set(profile_factory.chezmoi(
        rendered.config, "managed", "--include", "files"
    ).splitlines())
    entrypoint = profile_factory.chezmoi(
        rendered.config, "cat", str(Path.home() / ".hammerspoon/init.lua")
    )

    assert ".hammerspoon/init.lua" in managed
    assert ".hammerspoon/modules/displays.lua" in managed
    assert ".hammerspoon/modules/claude.lua" in managed
    assert "hammerspoon-macos-setup" not in entrypoint
    assert "/Users/" not in entrypoint
    assert 'dofile(hs.configdir .. "/modules/core.lua")' in entrypoint

    audio_files = {
        ".hammerspoon/audio_check.lua",
        ".hammerspoon/audio_check_impl.lua",
        ".hammerspoon/bin/mic_level",
        ".hammerspoon/bin/mic_level.swift",
    }
    if profile == "personal":
        assert audio_files <= managed
        assert 'dofile(hs.configdir .. "/audio_check.lua")' in entrypoint
    else:
        assert audio_files.isdisjoint(managed)
        assert "/audio_check.lua" not in entrypoint


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


def test_meter_compiles_once_and_recovers_after_failed_rebuild(tmp_path):
    source_dir = tmp_path / "hammerspoon/bin"
    source_dir.mkdir(parents=True)
    shutil.copy2(METER, source_dir / "mic_level")
    shutil.copy2(METER.parent / "mic_level.swift", source_dir / "mic_level.swift")
    compiler_bin = tmp_path / "fake-bin"
    compiler_bin.mkdir()
    compiler = compiler_bin / "swiftc"
    log = tmp_path / "compiler-calls"
    fake_executable = tmp_path / "fake-executable"
    fake_executable.write_text("#!/bin/sh\necho mic-value\n")
    fake_executable.chmod(0o755)
    compiler.write_text(
        "#!/bin/sh\n"
        'echo build >> "$SWIFTC_LOG"\n'
        'cp "$MIC_FAKE_EXE" "$3"\n'
    )
    compiler.chmod(0o755)
    env = {
        **os.environ, "HOME": str(tmp_path),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "PATH": f"{compiler_bin}:{os.environ['PATH']}",
        "SWIFTC_LOG": str(log),
        "MIC_FAKE_EXE": str(fake_executable),
    }

    def run():
        return subprocess.run(
            [str(source_dir / "mic_level")], env=env, capture_output=True, text=True
        )

    first = run()
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == "mic-value"
    assert run().returncode == 0
    assert log.read_text().splitlines() == ["build"]

    # A failed rebuild must keep the last working cached binary.
    compiled = tmp_path / "cache/hammerspoon/mic_level"
    source = source_dir / "mic_level.swift"
    os.utime(source, (compiled.stat().st_mtime + 5,) * 2)
    compiler.write_text("#!/bin/sh\nexit 17\n")
    assert run().returncode == 17
    assert compiled.exists() and os.access(compiled, os.X_OK)
    compiler.write_text(
        "#!/bin/sh\n"
        'echo build >> "$SWIFTC_LOG"\n'
        'cp "$MIC_FAKE_EXE" "$3"\n'
    )
    assert run().returncode == 0
    assert log.read_text().splitlines() == ["build", "build"]


def test_meter_shell_syntax():
    subprocess.run(["/bin/sh", "-n", str(METER)], check=True)


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
    assert (directory / "audio_check.lua").is_file()
    assert os.access(directory / "bin/mic_level", os.X_OK)
    assert (directory / "Spoons/keep.txt").read_text() == "unmanaged"
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    assert (directory / "Spoons/keep.txt").read_text() == "unmanaged"
