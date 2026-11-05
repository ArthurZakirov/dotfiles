"""The global Codex Voice hotkey targets only Warp and restores focus."""

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LUAJIT = shutil.which("luajit")
SCENARIOS = ROOT / "tests/support/hammerspoon_codex_voice_scenarios.lua"
MODULE = ROOT / "home/dot_hammerspoon/modules/codex_voice.lua"

pytestmark = pytest.mark.skipif(LUAJIT is None, reason="LuaJIT is required")


@pytest.mark.parametrize(
    "scenario",
    [
        "editor_background",
        "already_in_warp",
        "duplicate",
        "warp_missing",
        "no_terminal",
        "focus_blocked",
    ],
)
def test_global_voice_hotkey_only_sends_to_warp(scenario):
    result = subprocess.run(
        [LUAJIT, str(SCENARIOS), str(MODULE), scenario],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert f"PASS {scenario}" in result.stdout
