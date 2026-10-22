"""ChatGPT guidance stays in its repo source; apply prints a manual handoff."""

import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/chatgpt/personalization-instructions.md"
HOOK = ROOT / "home/run_after_90-chatgpt-personalization.sh.tmpl"
OBSOLETE_DESTINATION = ".config/chatgpt/personalization-instructions.md"
SETTINGS_URL = "https://chatgpt.com/settings/personalization?instructions=chatgpt"


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_personalization_source_and_manual_apply_reminder(profile, tmp_path, profile_factory):
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
    assert OBSOLETE_DESTINATION not in managed
    assert not (ROOT / "home/dot_config/chatgpt").exists()
    assert SOURCE.is_file()
    assert len(SOURCE.read_text()) < 5000
    assert "MCP tools are not exposed in this chat" in SOURCE.read_text()
    assert "Custom Instructions cannot activate a plugin" in SOURCE.read_text()

    # An existing untracked local file must not be overwritten by the reminder.
    local_copy = home / OBSOLETE_DESTINATION
    local_copy.parent.mkdir(parents=True)
    local_copy.write_text("unmanaged user content\n")
    before_source, before_local = SOURCE.read_bytes(), local_copy.read_bytes()

    hook = tmp_path / f"{profile}-after-apply.sh"
    hook.write_text(chezmoi("execute-template", "--file", str(HOOK)))
    subprocess.run(["sh", "-n", str(hook)], check=True)
    result = subprocess.run(
        ["sh", str(hook)], env={**os.environ, "HOME": str(home)},
        text=True, capture_output=True, check=True,
    )
    assert SOURCE.read_bytes() == before_source
    assert local_copy.read_bytes() == before_local
    if profile == "personal":
        assert f"Instructions file: {SOURCE}" in result.stdout
        assert SETTINGS_URL in result.stdout
        assert "manually" in result.stdout
        assert str(local_copy) not in result.stdout
    else:
        assert result.stdout == ""
        assert result.stderr == ""
