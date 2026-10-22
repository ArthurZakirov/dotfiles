"""ChatGPT instructions deployment and manual handoff, without account writes."""

import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "home/dot_config/chatgpt/personalization-instructions.md"
HOOK = ROOT / "home/run_after_90-chatgpt-personalization.sh.tmpl"
DESTINATION = ".config/chatgpt/personalization-instructions.md"
SETTINGS_URL = "https://chatgpt.com/settings/personalization?instructions=chatgpt"


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_personalization_deployment_and_apply_reminder(profile, tmp_path, profile_factory):
    rendered = profile_factory.render(profile)
    home = tmp_path / "Mac home with spaces"
    home.mkdir()

    def chezmoi(*args):
        return subprocess.run(
            ["chezmoi", "--source", str(ROOT / "home"),
             "--config", str(rendered.config), "--destination", str(home), *args],
            text=True, capture_output=True, check=True, timeout=30,
        ).stdout

    managed = chezmoi("managed", "--include", "files").splitlines()
    assert (DESTINATION in managed) == (profile == "personal")

    instructions = home / DESTINATION
    if profile == "personal":
        assert chezmoi("cat", str(instructions)) == SOURCE.read_text()
        assert len(SOURCE.read_text()) < 5000
        assert "MCP tools are not exposed in this chat" in SOURCE.read_text()
        assert "Custom Instructions cannot activate a plugin" in SOURCE.read_text()
        instructions.parent.mkdir(parents=True)
        instructions.write_text(SOURCE.read_text())
    else:
        # Even a pre-existing unmanaged personal file must be left untouched.
        instructions.parent.mkdir(parents=True)
        instructions.write_text("not managed in professional profile\n")

    hook = tmp_path / f"{profile}-after-apply.sh"
    hook.write_text(chezmoi("execute-template", "--file", str(HOOK)))
    subprocess.run(["sh", "-n", str(hook)], check=True)

    before = instructions.read_bytes()
    result = subprocess.run(
        ["sh", str(hook)], env={**os.environ, "HOME": str(home)},
        text=True, capture_output=True, check=True,
    )
    assert instructions.read_bytes() == before
    if profile == "personal":
        assert str(instructions) in result.stdout
        assert SETTINGS_URL in result.stdout
        assert "manually" in result.stdout
    else:
        assert result.stdout == ""
        assert result.stderr == ""
