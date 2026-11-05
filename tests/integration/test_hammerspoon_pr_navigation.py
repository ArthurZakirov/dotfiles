"""The PR navigation hotkey supports Chrome tabs and installed Chrome web apps."""

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
        pytest.param("bitbucket_comment", id="bitbucket-comment-permalink"),
        pytest.param("pwa_bitbucket_comment", id="bitbucket-pwa-comment-permalink"),
        pytest.param("chrome_stopped", id="chrome-not-running"),
        pytest.param("chrome_unreadable", id="browser-tab-unreadable"),
        pytest.param("pwa_github", id="github-installed-chrome-app"),
        pytest.param("pwa_focus_changed", id="pwa-remains-source-after-focus-change"),
        pytest.param("pwa_bitbucket_pr", id="bitbucket-installed-chrome-app"),
        pytest.param("pwa_string_url", id="pwa-accessibility-string-url"),
        pytest.param("pwa_nested_group", id="pwa-nested-accessibility-group"),
        pytest.param("pwa_windows_fallback", id="pwa-fallback-to-app-window"),
        pytest.param("pwa_unreadable", id="pwa-unreadable-url-never-uses-chrome-tab"),
        pytest.param("pwa_ax_error", id="pwa-accessibility-denied"),
    ],
)
def test_pr_hotkey_reads_source_browser_url_after_modifiers_release(scenario):
    result = subprocess.run(
        [LUA, str(SCENARIOS), str(CONFIG), scenario],
        capture_output=True, text=True, timeout=10,
    )

    assert result.returncode == 0, result.stderr
