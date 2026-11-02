"""The desktop keyboard action never invokes a model or guesses a Codex session."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LUAJIT = shutil.which("luajit")
SCENARIOS = ROOT / "tests/support/hammerspoon_agents_freshness_scenarios.lua"
HAMMERSPOON = ROOT / "home/dot_hammerspoon"

pytestmark = pytest.mark.skipif(LUAJIT is None, reason="LuaJIT required")


@pytest.mark.parametrize(
    "scenario",
    [
        "current",
        "outdated",
        "local_stale",
        "deployed_stale",
        "no_snapshot",
        "no_link",
        "wrong_link",
        "wrong_app",
        "multi_clipboard",
        "checker_missing",
        "corrupt_json",
        "checker_error",
    ],
)
def test_desktop_freshness_hotkey(scenario):
    result = subprocess.run(
        [LUAJIT, str(SCENARIOS), str(HAMMERSPOON), scenario],
        check=False, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr + result.stdout


@pytest.mark.parametrize("profile", ("personal", "professional"))
def test_hammerspoon_module_is_chezmoi_managed(profile, profile_factory):
    rendered = profile_factory.render(profile)
    files = profile_factory.chezmoi(rendered.config, "managed", "--include", "files")
    assert ".hammerspoon/modules/agents_freshness.lua" in files.splitlines()
    assert ".hammerspoon/bin/agents_md_pipeline" in files.splitlines()
