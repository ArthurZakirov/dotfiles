"""Both macOS profiles render the same managed, credential-isolated LaunchAgent."""

import plistlib
from pathlib import Path

import pytest


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_managed_launch_agent(profile_factory, profile):
    rendered = profile_factory.render(profile)

    xml = profile_factory.chezmoi(
        rendered.config,
        "cat",
        str(Path.home() / "Library/LaunchAgents/com.arthur.storage-maintenance.plist"),
    )
    agent = plistlib.loads(xml.encode())

    assert agent["Label"] == "com.arthur.storage-maintenance"
    assert agent["StartInterval"] == 86400
    assert agent["RunAtLoad"] is True
    assert agent["ProgramArguments"] == [
        "/usr/bin/env", "-i", f"HOME={Path.home()}", "PATH=/usr/bin:/bin",
        "/usr/bin/python3",
        f"{Path.home()}/.local/share/storage-maintenance/clean_chrome_clones.py",
    ]


def test_installer_syntax():
    import subprocess

    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        ["/bin/sh", "-n", str(root / "home/run_after_65-ensure-storage-maintenance.sh")],
        check=True,
    )
