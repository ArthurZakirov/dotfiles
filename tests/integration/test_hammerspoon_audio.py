"""Audio shortcut behavior with the production Lua module and a simulated Hammerspoon host."""

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LUA = shutil.which("luajit")
SCENARIOS = ROOT / "tests/support/hammerspoon_audio_scenarios.lua"
CONFIG = ROOT / "home/dot_hammerspoon"

pytestmark = pytest.mark.skipif(LUA is None, reason="LuaJIT is required to exercise Hammerspoon Lua modules")


@pytest.mark.parametrize(
    ("mute_state", "expected_message"),
    [
        pytest.param("muted", "Stumm", id="muted"),
        pytest.param("unmuted", "Nicht stumm", id="unmuted"),
        pytest.param("unknown", "Nicht verfügbar", id="unknown"),
    ],
)
def test_audio_shortcut_displays_reported_input_and_output_mute_states(mute_state, expected_message):
    result = subprocess.run(
        [LUA, str(SCENARIOS), str(CONFIG), "mute", mute_state, expected_message],
        text=True, capture_output=True, timeout=10,
    )

    assert result.returncode == 0, result.stderr


def test_restarting_audio_check_while_pending_starts_only_the_latest_meter():
    result = subprocess.run(
        [LUA, str(SCENARIOS), str(CONFIG), "restart_pending", "unknown"],
        text=True, capture_output=True, timeout=10,
    )

    assert result.returncode == 0, result.stderr


def test_restarting_audio_check_ignores_previous_meter_callbacks():
    result = subprocess.run(
        [LUA, str(SCENARIOS), str(CONFIG), "restart_active", "unknown"],
        text=True, capture_output=True, timeout=10,
    )

    assert result.returncode == 0, result.stderr


def test_audio_check_reports_when_no_microphone_signal_is_detected():
    result = subprocess.run(
        [LUA, str(SCENARIOS), str(CONFIG), "no_signal", "unknown"],
        text=True, capture_output=True, timeout=10,
    )

    assert result.returncode == 0, result.stderr
