"""Pre-apply snapshots protect existing dotfiles independent of checkout layout."""
from pathlib import Path
import json
import shutil
import os
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("checkout_name", ["regular checkout", "a clone with spaces"])
def test_existing_managed_files_are_preserved_before_apply(tmp_path, checkout_name):
    checkout = tmp_path / checkout_name
    source = checkout / "home"
    source.mkdir(parents=True)
    (checkout / "src").mkdir()
    shutil.copy2(ROOT / "src/backup-managed.sh", checkout / "src/backup-managed.sh")
    (source / "dot_example").write_text("new configuration\n")
    (source / "symlink_dot_reference").write_text("other-location")
    config = tmp_path / "chezmoi.toml"
    config.write_text(f'sourceDir = "{source}"\n')
    home = tmp_path / "destination home"
    home.mkdir()
    (home / ".example").write_text("existing manual configuration\n")
    (home / ".reference").symlink_to("other-location")
    hook = tmp_path / "preapply.sh"
    hook.write_text(subprocess.check_output([
        "chezmoi", "--config", str(config), "--source", str(source),
        "--working-tree", str(checkout), "--destination", str(home),
        "execute-template", "--file", str(ROOT / "home/run_before_01-snapshot-existing-managed.sh.tmpl"),
    ], text=True))

    proc = subprocess.run(["/bin/bash", str(hook)], capture_output=True, text=True,
                          env={**os.environ, "HOME": str(home)}, timeout=20)
    assert proc.returncode == 0, proc.stderr
    backups = list((home / "Library/Application Support/dotfiles/backups").glob("apply.*"))
    assert len(backups) == 1
    backup = backups[0] / "files"
    assert (backup / ".example").read_text() == "existing manual configuration\n"
    assert (backup / ".reference").is_symlink()
    assert os.readlink(backup / ".reference") == "other-location"
    assert (home / ".example").read_text() == "existing manual configuration\n"


def test_no_changes_creates_no_backup(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "dot_example").write_text("unchanged\n")
    home = tmp_path / "home"
    home.mkdir()
    (home / ".example").write_text("unchanged\n")
    config = tmp_path / "config.toml"
    config.write_text(f'sourceDir = "{source}"\n')
    script = ROOT / "src/backup-managed.sh"
    proc = subprocess.run(["/bin/bash", "-c",
                           'source "$1"; snapshot_existing_managed "$2" "$3" "$4" "$5"',
                           "test", str(script), str(config), str(source), str(source.parent), str(home)],
                          env={**os.environ, "HOME": str(home)}, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    assert not (home / "Library/Application Support/dotfiles/backups").exists()


def test_real_chezmoi_dry_run_and_apply_preserve_existing_state(tmp_path):
    """A non-Git checkout changes nothing in dry run and keeps an apply backup."""
    checkout = tmp_path / "checkout without git"
    source = checkout / "home"
    source.mkdir(parents=True)
    (checkout / "src").mkdir()
    shutil.copy2(ROOT / "src/backup-managed.sh", checkout / "src/backup-managed.sh")
    shutil.copy2(
        ROOT / "home/run_before_01-snapshot-existing-managed.sh.tmpl",
        source / "run_before_01-snapshot-existing-managed.sh.tmpl",
    )
    (source / "dot_example").write_text("new managed state\n")
    config = tmp_path / "config.toml"
    config.write_text(f'sourceDir = "{source}"\n')
    home = tmp_path / "home with spaces"
    home.mkdir()
    target = home / ".example"
    target.write_text("old user content\n")

    command = ["chezmoi", "--config", str(config), "--source", str(source),
               "--working-tree", str(checkout), "--destination", str(home)]
    env = {**os.environ, "HOME": str(home)}

    preview = subprocess.run(command + ["apply", "--dry-run", "--verbose"],
                             text=True, capture_output=True, env=env, timeout=20)
    assert preview.returncode == 0, preview.stderr
    assert target.read_text() == "old user content\n"
    assert not (home / "Library/Application Support/dotfiles/backups").exists()

    apply = subprocess.run(command + ["apply"], text=True, capture_output=True,
                           env=env, timeout=20)
    assert apply.returncode == 0, apply.stderr
    assert target.read_text() == "new managed state\n"
    backups = list((home / "Library/Application Support/dotfiles/backups").glob("apply.*"))
    assert len(backups) == 1
    assert (backups[0] / "files/.example").read_text() == "old user content\n"

    again = subprocess.run(command + ["apply"], text=True, capture_output=True,
                           env=env, timeout=20)
    assert again.returncode == 0, again.stderr
    assert target.read_text() == "new managed state\n"
    assert len(list((home / "Library/Application Support/dotfiles/backups").glob("apply.*"))) == 1


@pytest.mark.parametrize("root_source", ["default", "environment", "configured"])
def test_preapply_backup_accepts_legacy_config_without_repos_dir(tmp_path, root_source):
    # Arrange: an existing chezmoi config with no reposDir, plus a managed
    # target that must be backed up before being replaced.
    checkout = tmp_path / "dotfiles checkout"
    source = checkout / "home"
    template = source / "dot_config/repo-refresh/private_config.json.tmpl"
    template.parent.mkdir(parents=True)
    (checkout / "src").mkdir()
    shutil.copy2(ROOT / "src/backup-managed.sh", checkout / "src/backup-managed.sh")
    shutil.copy2(
        ROOT / "home/run_before_01-snapshot-existing-managed.sh.tmpl",
        source / "run_before_01-snapshot-existing-managed.sh.tmpl",
    )
    shutil.copy2(
        ROOT / "home/dot_config/repo-refresh/private_config.json.tmpl", template,
    )
    (source / ".chezmoidata.toml").write_text("[repoRefresh]\nenabled = true\n")

    home = tmp_path / "destination home"
    home.mkdir()
    target = home / ".config/repo-refresh/config.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"previous": "preserve this"}\n')

    custom_root = tmp_path / "custom repository root"
    environment_root = tmp_path / "environment repository root"
    config = tmp_path / "legacy-config.toml"
    config.write_text(
        f'sourceDir = "{source}"\n'
        "[data]\nprofile = \"personal\"\n"
        + (f'reposDir = "{custom_root}"\n' if root_source == "configured" else "")
    )
    expected_root = {
        "default": home / "Repos",
        "environment": environment_root,
        "configured": custom_root,
    }[root_source]
    command = [
        "chezmoi", "--config", str(config), "--source", str(source),
        "--working-tree", str(checkout), "--destination", str(home),
    ]
    env = {**os.environ, "HOME": str(home)}
    env.pop("REPOS_DIR", None)
    if root_source != "default":
        env["REPOS_DIR"] = str(environment_root)

    # Act: execute the real chezmoi apply, including the pre-apply backup hook.
    result = subprocess.run(
        command + ["apply"], env=env, text=True, capture_output=True, timeout=30,
    )

    # Assert: rendering succeeds, the original file is saved, and the expected
    # configured or default repository path reaches the installed target.
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(target.read_text()) == {
        "enabled": True, "root": str(expected_root), "remote": "origin",
        "archiveRecoveries": True,
    }
    backups = list((home / "Library/Application Support/dotfiles/backups").glob("apply.*"))
    assert len(backups) == 1
    assert (backups[0] / "files/.config/repo-refresh/config.json").read_text() == (
        '{"previous": "preserve this"}\n'
    )


def test_backup_rejects_managed_path_through_external_parent_symlink(tmp_path):
    """A lexical destination prefix cannot authorize following a parent symlink."""
    source = tmp_path / "repository" / "home"
    source.mkdir(parents=True)
    nested = source / "dot_link"
    nested.mkdir()
    (nested / "dot_private").write_text("new managed content\n")
    home = tmp_path / "destination"
    home.mkdir()
    outside = tmp_path / "external"
    outside.mkdir()
    (outside / ".private").write_text("sensitive external content\n")
    (home / ".link").symlink_to(outside, target_is_directory=True)
    config = tmp_path / "chezmoi.toml"
    config.write_text(f'sourceDir = "{source}"\n')

    script = ROOT / "src/backup-managed.sh"
    result = subprocess.run(
        ["/bin/bash", "-c", 'source "$1"; snapshot_existing_managed "$2" "$3" "$4" "$5"',
         "test", str(script), str(config), str(source), str(source.parent), str(home)],
        env={**os.environ, "HOME": str(home)}, text=True, capture_output=True, timeout=20,
    )
    assert result.returncode != 0
    assert "target resolves outside destination" in result.stderr
    assert not (home / "Library/Application Support/dotfiles/backups").exists()
    assert (outside / ".private").read_text() == "sensitive external content\n"
