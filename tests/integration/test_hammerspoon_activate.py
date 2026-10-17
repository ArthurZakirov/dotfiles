"""End-to-end activation CLI against process and Hammerspoon IPC seams."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.support.hammerspoon_process import executable

ROOT = Path(__file__).resolve().parents[2]
ACTIVATE = ROOT / "home/dot_local/bin/executable_hammerspoon-activate"


@pytest.fixture
def simulated_hammerspoon(tmp_path):
    app = tmp_path / "Hammerspoon.app"
    app.mkdir()
    cli_dir = tmp_path / "fake-bin"
    cli_dir.mkdir()
    nonce_path = tmp_path / "last-activated-nonce"
    log = tmp_path / "events"
    executable(cli_dir, "pgrep", 'test "$HAMMERSPOON_ALREADY_RUNNING" = 1\n')
    executable(cli_dir, "open", 'echo launched >> "$HAMMERSPOON_TEST_LOG"\n')
    cli = cli_dir / "hs"
    cli.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, re, sys\n"
        "command = sys.argv[2]\n"
        "if 'dotfiles-ipc-ready' in command:\n"
        "    print('dotfiles-ipc-ready')\n"
        "elif 'dotfiles.activation_nonce' in command:\n"
        "    nonce = re.search(r'activation_nonce\\\", \\\"([a-f0-9]+)', command)\n"
        "    assert nonce, command\n"
        "    pathlib.Path(os.environ['HAMMERSPOON_TEST_NONCE']).write_text(nonce.group(1))\n"
        "    with open(os.environ['HAMMERSPOON_TEST_LOG'], 'a') as log: log.write('reloaded\\n')\n"
        "else: sys.exit(1)\n"
    )
    cli.chmod(0o755)
    verifier = executable(
        cli_dir,
        "verify",
        'test "$1" = --nonce && test "$(cat "$HAMMERSPOON_TEST_NONCE")" = "$2" || exit 3\n'
        'echo "Hammerspoon: config ready"\n',
    )
    env = {
        **os.environ,
        "PATH": f"{cli_dir}:{os.environ['PATH']}",
        "HAMMERSPOON_APP_PATH": str(app),
        "HAMMERSPOON_VERIFY_BIN": str(verifier),
        "HAMMERSPOON_TEST_NONCE": str(nonce_path),
        "HAMMERSPOON_TEST_LOG": str(log),
    }
    return env, log, nonce_path


@pytest.mark.parametrize(
    ("already_running", "expected_events"),
    [
        pytest.param(True, ["reloaded"], id="running"),
        pytest.param(False, ["launched", "reloaded"], id="stopped"),
    ],
)
def test_activation_makes_new_configuration_ready(
    simulated_hammerspoon, already_running, expected_events,
):
    env, log, nonce = simulated_hammerspoon
    env["HAMMERSPOON_ALREADY_RUNNING"] = "1" if already_running else "0"

    result = subprocess.run(
        [sys.executable, str(ACTIVATE)], env=env,
        capture_output=True, text=True, timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "applied configuration is active" in result.stdout
    assert log.read_text().splitlines() == expected_events
    assert len(nonce.read_text()) == 32


def test_activation_fails_without_a_reachable_hammerspoon_cli(tmp_path):
    app = tmp_path / "Hammerspoon.app"
    app.mkdir()
    env = {
        "HOME": str(tmp_path),
        "PATH": "/usr/bin:/bin",
        "HAMMERSPOON_APP_PATH": str(app),
    }

    result = subprocess.run(
        [sys.executable, str(ACTIVATE)], env=env,
        capture_output=True, text=True, timeout=10,
    )

    assert result.returncode != 0
    assert "CLI unavailable" in result.stderr
