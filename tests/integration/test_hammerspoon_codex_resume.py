"""Ctrl-Option-Command-W exercises the shared real Lua modules."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LUAJIT = shutil.which("luajit")
SCENARIOS = ROOT / "tests/support/hammerspoon_codex_resume_scenarios.lua"
HOMEDIR = ROOT / "home/dot_hammerspoon"


@pytest.mark.skipif(not LUAJIT, reason="LuaJIT required")
@pytest.mark.parametrize("scenario", (
    "success", "wrong_app", "multi_clipboard", "no_link", "invalid_link",
    "missing_launcher", "task_fails_start", "task_returns_error", "overlap",
    "already_closed", "quit_delayed", "quit_refused",
))
def test_codex_desktop_resume_hotkey(scenario):
    result = subprocess.run(
        [LUAJIT, str(SCENARIOS), str(HOMEDIR), scenario],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode == 0, result.stderr + result.stdout

def test_launcher_is_chezmoi_managed(profile_factory):
    for profile in ("personal", "professional"):
        rendered = profile_factory.render(profile)
        paths = profile_factory.chezmoi(rendered.config, "managed", "--include", "files")
        items = set(paths.splitlines())
        assert ".hammerspoon/bin/codex_resume_warp" in items
        assert ".hammerspoon/modules/codex_resume.lua" in items
        assert ".hammerspoon/modules/codex_desktop_session.lua" in items
