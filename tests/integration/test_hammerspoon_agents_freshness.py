"""The desktop keyboard action never invokes a model or guesses a Codex session."""
import json
import os
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
        "intel_homebrew",
        "python_missing",
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
    assert ".codex/hooks-json/agents-md-freshness/check.py" in files.splitlines()



@pytest.mark.parametrize("profile", ("personal", "professional"))
def test_new_chezmoi_install_includes_runnable_session_checker(
    tmp_path, profile_factory, profile,
):
    # The destination has no installed checker and no inherited chezmoi config.
    rendered = profile_factory.render(profile)
    target = tmp_path / ".codex/hooks-json/agents-md-freshness/check.py"
    target.parent.mkdir(parents=True)
    assert not target.exists()

    deployed = subprocess.run(
        [
            "chezmoi", "--source", str(ROOT / "home"),
            "--config", str(rendered.config),
            "--destination", str(tmp_path), "apply", str(target),
        ],
        env={**os.environ, "HOME": str(tmp_path)},
        capture_output=True, text=True, timeout=15,
    )

    assert deployed.returncode == 0, deployed.stderr
    assert target.is_file()
    assert target.stat().st_mode & 0o111

    invoked = subprocess.run(
        [
            str(target), "--check",
            "--session-id", "01a1935b-e50c-7d52-a754-3f81fdffcaee",
            "--codex-home", str(tmp_path / ".codex"),
        ],
        capture_output=True, text=True, timeout=5,
    )

    assert invoked.returncode == 0, invoked.stderr
    assert json.loads(invoked.stdout)["status"] == "unknown"
    assert "transcript" in json.loads(invoked.stdout)["reason"].lower()
