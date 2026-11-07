"""Option+2 only clicks the current conversation's voice controls."""

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LUAJIT = shutil.which("luajit")
SCENARIOS = ROOT / "tests/support/hammerspoon_chatgpt_voice_scenarios.lua"
MODULE = ROOT / "home/dot_hammerspoon/modules/chatgpt_voice.lua"

pytestmark = pytest.mark.skipif(LUAJIT is None, reason="LuaJIT is required")


@pytest.mark.parametrize(
    "scenario",
    [
        "start",
        "end",
        "cancel",
        "prefer_end",
        "double",
        "empty_chat",
        "new_voice",
        "dictation",
        "disabled",
        "no_bounds",
        "wrong_app",
        "focus_changed",
    ],
)
def test_option_two_operates_only_current_chat_voice_control(scenario):
    result = subprocess.run(
        [LUAJIT, str(SCENARIOS), str(MODULE), scenario],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"PASS {scenario}" in result.stdout
