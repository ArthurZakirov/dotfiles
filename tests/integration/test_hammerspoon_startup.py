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


def test_first_run_launches_once_and_never_restarts_running_app(tmp_path, fake_commands):
    app = tmp_path / "Hammerspoon.app"
    app.mkdir()
    log = tmp_path / "calls.log"
    executable(fake_commands, "uname", "echo Darwin\n")
    executable(fake_commands, "launchctl", 'test "$1" = print\n')
    executable(
        fake_commands, "pgrep", 'test "$HAMMERSPOON_RUNNING" = 1\n'
    )
    executable(fake_commands, "open", 'echo open >> "$HAMMERSPOON_TEST_LOG"\n')
    checker = executable(
        fake_commands, "verify", 'echo verify >> "$HAMMERSPOON_TEST_LOG"\n'
    )
    setup = executable(
        fake_commands, "swift-setup", 'echo swift >> "$HAMMERSPOON_TEST_LOG"\n'
    )
    env = {
        **os.environ,
        "PATH": f"{fake_commands}:{os.environ['PATH']}",
        "HAMMERSPOON_SWIFTC_HELPER": str(setup),
        "HAMMERSPOON_APP_PATH": str(app),
        "HAMMERSPOON_VERIFY_BIN": str(checker),
        "HAMMERSPOON_TEST_LOG": str(log),
        "HAMMERSPOON_RUNNING": "0",
        "DOTFILES_SKIP_OPTIONAL_APPS": "0",
    }

    subprocess.run(["/bin/bash", str(HOOK)], env=env, check=True)
    assert log.read_text().splitlines() == ["swift", "open", "verify"]
    env["HAMMERSPOON_RUNNING"] = "1"
    subprocess.run(["/bin/bash", str(HOOK)], env=env, check=True)
    assert log.read_text().splitlines() == ["swift", "open", "verify", "swift", "verify"]

    env["DOTFILES_SKIP_OPTIONAL_APPS"] = "1"
    subprocess.run(["/bin/bash", str(HOOK)], env=env, check=True)
    assert log.read_text().splitlines() == ["swift", "open", "verify", "swift", "verify"]


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


def test_failed_hammerspoon_launch_does_not_interrupt_dotfiles_apply(tmp_path, fake_commands):
    app = tmp_path / "Hammerspoon.app"
    app.mkdir()
    log = tmp_path / "verify.log"
    executable(fake_commands, "uname", "echo Darwin\n")
    executable(fake_commands, "launchctl", 'test "$1" = print\n')
    executable(fake_commands, "pgrep", "exit 1\n")
    executable(fake_commands, "open", "exit 9\n")
    verifier = executable(
        fake_commands, "verify", 'echo verified >> "$HAMMERSPOON_TEST_LOG"\n'
    )
    env = {
        **os.environ,
        "PATH": f"{fake_commands}:{os.environ['PATH']}",
        "HAMMERSPOON_APP_PATH": str(app),
        "HAMMERSPOON_VERIFY_BIN": str(verifier),
        "HAMMERSPOON_TEST_LOG": str(log),
        "DOTFILES_SKIP_OPTIONAL_APPS": "0",
    }

    result = subprocess.run(
        ["/bin/bash", str(HOOK)], env=env, text=True, capture_output=True
    )

    assert result.returncode == 0
    assert "launch failed" in result.stderr
    assert log.read_text().strip() == "verified"
