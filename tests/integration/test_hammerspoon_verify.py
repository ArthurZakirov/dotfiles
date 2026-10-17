"""Public hammerspoon-verify CLI status and failure behavior."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.support.hammerspoon_process import executable

VERIFY = Path(__file__).resolve().parents[2] / "home/dot_local/bin/executable_hammerspoon-verify"


@pytest.fixture
def fake_commands(tmp_path):
    directory = tmp_path / "fake-bin"
    directory.mkdir()
    return directory


@pytest.mark.parametrize(
    ("state", "success"),
    [
        pytest.param(dict(accessibility=True, autolaunch=True, audio=True, ready=True, nonce="", hotkeys=24), True, id="ready"),
        pytest.param(dict(accessibility=False, autolaunch=True, audio=True, ready=True, nonce="", hotkeys=24), False, id="accessibility-denied"),
        pytest.param(dict(accessibility=True, autolaunch=True, audio=False, ready=True, nonce="", hotkeys=24), False, id="audio-not-loaded"),
        pytest.param(dict(accessibility=True, autolaunch=True, audio=True, ready=True, nonce="", hotkeys=0), False, id="no-hotkeys"),
    ],
)
def test_runtime_verifier_reports_config_state(fake_commands, state, success):
    executable(fake_commands, "hs", 'printf "%s\\n" "$HS_TEST_RESULT"\n')
    env = {
        **os.environ, "PATH": f"{fake_commands}:{os.environ['PATH']}",
        "HS_TEST_RESULT": json.dumps(state),
    }
    result = subprocess.run([str(VERIFY)], env=env, text=True, capture_output=True)
    assert (result.returncode == 0) is success
    assert f"registered_hotkeys={state['hotkeys']}" in result.stdout
    assert f"audio_check={str(state['audio'])}" in result.stdout


def test_verifier_reports_invalid_ipc_response(fake_commands):
    executable(fake_commands, "hs", "printf 'not-json\\n'\n")
    result = subprocess.run(
        [str(VERIFY)], text=True, capture_output=True,
        env={**os.environ, "PATH": f"{fake_commands}:{os.environ['PATH']}"},
    )
    assert result.returncode != 0
    assert "invalid runtime response" in result.stderr


def test_verifier_uses_bundled_cli_without_global_hs_symlink(tmp_path):
    app = tmp_path / "Hammerspoon.app"
    bundled_dir = app / "Contents/Frameworks/hs"
    bundled_dir.mkdir(parents=True)
    executable(
        bundled_dir, "hs",
        'printf "%s\\n" "$HS_TEST_RESULT"\n',
    )
    env = {
        **os.environ,
        "HAMMERSPOON_APP_PATH": str(app),
        "HS_TEST_RESULT": json.dumps(
            dict(accessibility=True, autolaunch=True, audio=True, ready=True, nonce="", hotkeys=18)
        ),
        "PATH": "/usr/bin:/bin",
    }
    result = subprocess.run(
        [sys.executable, str(VERIFY)], env=env, text=True, capture_output=True
    )
    assert result.returncode == 0, result.stderr
    assert "audio_check=True" in result.stdout
    assert "registered_hotkeys=18" in result.stdout


def test_verifier_rejects_a_stale_configuration_nonce(fake_commands):
    executable(fake_commands, "hs", 'printf "%s\\n" "$HS_TEST_RESULT"\n')
    env = {
        **os.environ,
        "PATH": f"{fake_commands}:{os.environ['PATH']}",
        "HS_TEST_RESULT": json.dumps(dict(
            accessibility=True, autolaunch=True, audio=True,
            ready=True, nonce="old", hotkeys=30,
        )),
    }

    result = subprocess.run(
        [str(VERIFY), "--nonce", "new"], env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert "config_ready=True" in result.stdout
