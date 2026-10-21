"""Exercise first-run automation without launching the developer's Hammerspoon."""

import os
from pathlib import Path
import subprocess

import pytest

from tests.support.hammerspoon_process import executable


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "home/run_after_30-ensure-hammerspoon.sh"


@pytest.fixture
def fake_commands(tmp_path):
    directory = tmp_path / "fake-bin"
    directory.mkdir()
    return directory


def test_apply_activates_hammerspoon_with_a_running_or_stopped_app(tmp_path, fake_commands):
    app = tmp_path / "Hammerspoon.app"
    app.mkdir()
    log = tmp_path / "calls.log"
    executable(fake_commands, "uname", "echo Darwin\n")
    executable(fake_commands, "launchctl", 'test "$1" = print\n')
    activator = executable(
        fake_commands, "activate", 'echo activated >> "$HAMMERSPOON_TEST_LOG"\n'
    )
    setup = executable(
        fake_commands, "swift-setup", 'echo swift >> "$HAMMERSPOON_TEST_LOG"\n'
    )
    env = {
        **os.environ,
        "PATH": f"{fake_commands}:{os.environ['PATH']}",
        "HAMMERSPOON_SWIFTC_HELPER": str(setup),
        "HAMMERSPOON_ACTIVATE_BIN": str(activator),
        "HAMMERSPOON_APP_PATH": str(app),
        "HAMMERSPOON_TEST_LOG": str(log),
        "DOTFILES_SKIP_OPTIONAL_APPS": "0",
    }

    subprocess.run(["/bin/bash", str(HOOK)], env=env, check=True)
    subprocess.run(["/bin/bash", str(HOOK)], env=env, check=True)

    assert log.read_text().splitlines() == ["activated", "activated"]

    env["DOTFILES_SKIP_OPTIONAL_APPS"] = "1"
    subprocess.run(["/bin/bash", str(HOOK)], env=env, check=True)
    assert log.read_text().splitlines() == ["activated", "activated"]



def test_gui_launch_skips_when_no_session(tmp_path, fake_commands):
    app = tmp_path / "Hammerspoon.app"
    app.mkdir()
    log = tmp_path / "open.log"
    executable(fake_commands, "uname", "echo Darwin\n")
    executable(fake_commands, "launchctl", "exit 1\n")
    executable(fake_commands, "open", 'echo open >> "$HAMMERSPOON_TEST_LOG"\n')
    env = {
        **os.environ, "PATH": f"{fake_commands}:{os.environ['PATH']}",
        "HAMMERSPOON_APP_PATH": str(app),
        "HAMMERSPOON_TEST_LOG": str(log),
        "DOTFILES_SKIP_OPTIONAL_APPS": "0",
    }
    subprocess.run(["/bin/bash", str(HOOK)], env=env, check=True)
    assert not log.exists()


def test_apply_fails_when_new_hotkeys_cannot_be_verified(tmp_path, fake_commands):
    app = tmp_path / "Hammerspoon.app"
    app.mkdir()
    executable(fake_commands, "uname", "echo Darwin\n")
    executable(fake_commands, "launchctl", 'test "$1" = print\n')
    failing = executable(fake_commands, "activate", "exit 9\n")
    setup = executable(fake_commands, "swift-setup", "exit 0\n")
    env = {
        **os.environ,
        "PATH": f"{fake_commands}:{os.environ['PATH']}",
        "HAMMERSPOON_SWIFTC_HELPER": str(setup),
        "HAMMERSPOON_ACTIVATE_BIN": str(failing),
        "HAMMERSPOON_APP_PATH": str(app),
        "DOTFILES_SKIP_OPTIONAL_APPS": "0",
    }

    result = subprocess.run(["/bin/bash", str(HOOK)], env=env)

    assert result.returncode != 0
