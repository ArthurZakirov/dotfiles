"""Window-to-Space shortcut behavior with the production Lua module and simulated macOS effects."""

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LUA = shutil.which("luajit")
SCENARIOS = ROOT / "tests/support/hammerspoon_spaces_scenarios.lua"
CONFIG = ROOT / "home/dot_hammerspoon"

pytestmark = pytest.mark.skipif(LUA is None, reason="LuaJIT is required to exercise Hammerspoon Lua modules")


@pytest.mark.parametrize(
    "scenario",
    [
        pytest.param("move_failed", id="failed-move-timeout"),
        pytest.param("move_succeeded", id="successful-move"),
    ],
)
def test_space_move_releases_grabbed_window_and_stops_monitoring(scenario):
    result = subprocess.run(
        [LUA, str(SCENARIOS), str(CONFIG), scenario],
        text=True, capture_output=True, timeout=10,
    )

    assert result.returncode == 0, result.stderr
