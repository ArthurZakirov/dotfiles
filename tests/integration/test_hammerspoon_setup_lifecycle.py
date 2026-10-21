"""Hammerspoon setup through real chezmoi apply in an isolated home.

The actual chezmoi migration, file deployment, activation and verification run.
Only OS-owned Hammerspoon process and IPC interfaces are simulated. No change is
applied to the developer's HOME or running Hammerspoon instance.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests.support.hammerspoon_process import executable


ROOT = Path(__file__).resolve().parents[2]
MANAGED = ROOT / "home"


@pytest.fixture
def setup_environment(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    source = tmp_path / "chezmoi-source"
    source.mkdir()
    shutil.copytree(MANAGED / "dot_hammerspoon", source / "dot_hammerspoon")
    bin_source = source / "dot_local/bin"
    bin_source.mkdir(parents=True)
    for name in ("executable_hammerspoon-activate", "executable_hammerspoon-verify"):
        shutil.copy2(MANAGED / "dot_local/bin" / name, bin_source / name)
    for name in (
        "run_once_before_05-migrate-hammerspoon.sh",
        "run_after_30-ensure-hammerspoon.sh",
    ):
        shutil.copy2(MANAGED / name, source / name)

    root = home / ".hammerspoon"
    root.mkdir()
    (root / "Spoons").mkdir()
    (root / "Spoons/keep.lua").write_text("unmanaged spoon")
    local = home / ".hammerspoon-local"
    local.mkdir()
    (local / "init.lua").write_text("previous configuration")
    legacy = home / "Repos/private-hammerspoon"
    (legacy / "modules").mkdir(parents=True)
    (legacy / "bin").mkdir()
    (legacy / "init.lua").write_text("previous configuration")
    (legacy / "modules/core.lua").write_text("previous module")
    (root / "init.lua").symlink_to(legacy / "init.lua")
    (root / "modules").symlink_to(legacy / "modules", target_is_directory=True)
    (root / "bin").symlink_to(legacy / "bin", target_is_directory=True)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    events = tmp_path / "events.txt"
    runtime_nonce = tmp_path / "last-runtime-nonce"
    executable(fake_bin, "uname", "echo Darwin\n")
    executable(fake_bin, "launchctl", 'test "$1" = print\n')
    executable(fake_bin, "pgrep", 'test "$HAMMERSPOON_RUNNING" = 1 || test -f "$HAMMERSPOON_PROCESS_STARTED"\n')
    executable(fake_bin, "open", 'echo launched >> "$HAMMERSPOON_SETUP_EVENTS"; touch "$HAMMERSPOON_PROCESS_STARTED"\n')
    executable(fake_bin, "swift-setup", "exit 0\n")
    hs = fake_bin / "hs"
    hs.write_text(
        f"""#!{sys.executable}
import json
import os
from pathlib import Path
import sys

script = sys.argv[2]
nonce_file = Path(os.environ["HAMMERSPOON_SETUP_NONCE"])
if "dotfiles-ipc-ready" in script:
    print("dotfiles-ipc-ready")
elif 'hs.settings.set("dotfiles.activation_nonce"' in script:
    nonce = script.split('dotfiles.activation_nonce", "')[1].split('"')[0]
    nonce_file.write_text(nonce)
    with open(os.environ["HAMMERSPOON_SETUP_EVENTS"], "a") as stream:
        stream.write("reloaded\\n")
elif "hs.json.encode(" in script:
    nonce = nonce_file.read_text() if nonce_file.exists() else ""
    print(json.dumps(dict(
        accessibility=True, autolaunch=True, audio=True,
        ready=True, nonce=nonce, hotkeys=30,
    )))
else:
    sys.exit("Unknown Hammerspoon IPC request: " + script)
"""
    )
    hs.chmod(0o755)
    config = tmp_path / "chezmoi.toml"
    config.write_text("")

    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "HAMMERSPOON_APP_PATH": str(tmp_path / "Hammerspoon.app"),
        "HAMMERSPOON_SWIFTC_HELPER": str(fake_bin / "swift-setup"),
        "HAMMERSPOON_SETUP_NONCE": str(runtime_nonce),
        "HAMMERSPOON_PROCESS_STARTED": str(tmp_path / "started"),
        "HAMMERSPOON_SETUP_EVENTS": str(events),
    }
    (tmp_path / "Hammerspoon.app").mkdir()
    command = [
        "chezmoi", "--source", str(source), "--config", str(config),
        "--destination", str(home), "apply",
    ]
    return home, root, events, runtime_nonce, command, env


@pytest.mark.parametrize("layout", ["custom-symlinks", "regular-files", "root-symlink"])
@pytest.mark.parametrize(
    ("running", "expected_events"),
    [
        pytest.param(True, ["reloaded", "reloaded"], id="already-running"),
        pytest.param(False, ["launched", "reloaded", "reloaded"], id="initially-stopped"),
    ],
)
def test_apply_migrates_existing_config_and_reports_ready_runtime(
    setup_environment, running, expected_events, layout,
):
    home, root, events, runtime_nonce, command, env = setup_environment
    env["HAMMERSPOON_RUNNING"] = "1" if running else "0"
    if layout == "regular-files":
        for entry in ("init.lua", "modules", "bin"):
            path = root / entry
            if path.is_dir():
                original = path.resolve()
                path.unlink()
                shutil.copytree(original, path)
            else:
                original = path.read_text()
                path.unlink()
                path.write_text(original)
    elif layout == "root-symlink":
        original_root = home / "original-hammerspoon-directory"
        shutil.copytree(root, original_root, symlinks=True)
        shutil.rmtree(root)
        root.symlink_to(original_root, target_is_directory=True)

    first = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=40,
    )
    assert first.returncode == 0, first.stdout + first.stderr

    assert (root / "init.lua").read_text() == (MANAGED / "dot_hammerspoon/init.lua").read_text()
    assert not (root / "init.lua").is_symlink()
    assert (root / "modules/audio_check.lua").is_file()
    assert (root / "bin/mic_level").stat().st_mode & 0o111
    assert (root / "Spoons/keep.lua").read_text() == "unmanaged spoon"
    assert (home / ".hammerspoon-local/init.lua").read_text() == "previous configuration"
    backup_root = home / "Library/Application Support/dotfiles/backups"
    backups = list(backup_root.iterdir())
    assert len(backups) == 1
    if layout == "regular-files":
        assert (backups[0] / "hammerspoon/init.lua").read_text() == "previous configuration"
        assert (backups[0] / "hammerspoon/modules/core.lua").read_text() == "previous module"
        assert (root / "modules/core.lua").read_text() != "previous module"
    else:
        assert (backups[0] / "resolved/init.lua").read_text() == "previous configuration"
        assert (backups[0] / "resolved/modules/core.lua").read_text() == "previous module"
    if layout == "root-symlink":
        assert not root.is_symlink()
        assert (original_root / "init.lua").is_symlink()
        assert (backups[0] / "original-root-link").is_symlink()
    assert (home / ".cache/chezmoi/hammerspoon-migration-complete").is_file()
    first_nonce = runtime_nonce.read_text()
    assert len(first_nonce) == 32

    second = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=40,
    )
    assert second.returncode == 0, second.stdout + second.stderr

    assert events.read_text().splitlines() == expected_events
    assert len(list(backup_root.iterdir())) == 1
    assert (root / "Spoons/keep.lua").read_text() == "unmanaged spoon"
    assert runtime_nonce.read_text() != first_nonce


def test_apply_accepts_arbitrary_symlink_target_and_does_not_mutate_it(
    setup_environment,
):
    home, root, events, _, command, env = setup_environment
    original = home / "another-personal-config"
    original.mkdir()
    (original / "untouched.lua").write_text("do not touch")
    (root / "modules").unlink()
    (root / "modules").symlink_to(original, target_is_directory=True)
    env["HAMMERSPOON_RUNNING"] = "1"

    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=40,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (root / "modules").is_symlink()
    assert (root / "modules/audio_check.lua").is_file()
    assert (original / "untouched.lua").read_text() == "do not touch"
    assert (root / "Spoons/keep.lua").read_text() == "unmanaged spoon"
    backup_root = home / "Library/Application Support/dotfiles/backups"
    assert (next(backup_root.iterdir()) / "resolved/modules/untouched.lua").read_text() == "do not touch"
    assert events.read_text().splitlines() == ["reloaded"]
