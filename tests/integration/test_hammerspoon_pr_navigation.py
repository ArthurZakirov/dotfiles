"""The PR navigation hotkey routes the Chrome tab despite focus changes."""

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
LUA = shutil.which("luajit")
SCENARIOS = ROOT / "tests/support/hammerspoon_pr_navigation_scenarios.lua"
CONFIG = ROOT / "home/dot_hammerspoon"

pytestmark = pytest.mark.skipif(LUA is None, reason="LuaJIT is required for Hammerspoon module tests")


@pytest.mark.parametrize(
    "scenario",
    [
        pytest.param("chrome_focused", id="chrome-in-foreground"),
        pytest.param("chrome_background", id="chrome-background-after-key-release"),
        pytest.param("github_branch", id="github-branch-from-background"),
        pytest.param("bitbucket_pr", id="bitbucket-pr-from-background"),
        pytest.param("chrome_stopped", id="chrome-not-running"),
        pytest.param("chrome_unreadable", id="browser-tab-unreadable"),
    ],
)
def test_pr_hotkey_routes_chrome_tab_after_modifiers_release(scenario):
    result = subprocess.run(
        [LUA, str(SCENARIOS), str(CONFIG), scenario],
        capture_output=True, text=True, timeout=10,
    )

    assert result.returncode == 0, result.stderr
