"""Native keyboard shortcut setup is distributed to both macOS profiles."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_managed_shortcuts_are_available_to_each_profile(profile, profile_factory):
    # Arrange
    rendered = profile_factory.render(profile)

    # Act
    installed = profile_factory.chezmoi(rendered.config, "managed", "--include", "files")

    # Assert
    assert ".config/macos-shortcuts/shortcuts.json" in installed
    assert ".local/bin/macos-shortcuts" in installed


def test_native_shortcuts_profile_matches_export_schema():
    # Arrange
    source = ROOT / "home/dot_config/macos-shortcuts/shortcuts.json"

    # Act
    profile = json.loads(source.read_text())

    # Assert
    assert profile["version"] == 1
    assert profile["system_hotkeys"]
    assert profile["app_shortcuts"]["com.openai.codex"]["New Window"] == "@$n"
    assert profile["service_shortcuts"]
    assert profile["accessibility_hotkeys"]


def test_macos_defaults_import_preserves_native_hotkey_types_and_other_settings(tmp_path):
    """Real macOS defaults commands, isolated to disposable preference plists."""
    import plistlib
    import subprocess

    domain = tmp_path / "sample.plist"
    source = tmp_path / "merged.plist"
    subprocess.run(["defaults", "write", str(domain), "OtherPreference", "-int", "37"],
                   check=True, capture_output=True)
    exported = subprocess.run(["defaults", "export", str(domain), "-"],
                              check=True, capture_output=True).stdout
    prefs = plistlib.loads(exported)
    prefs["AppleSymbolicHotKeys"] = {
        "15": {"enabled": True, "value": {"type": "standard", "parameters": [56, 28, 1572864]}},
        "164": {"enabled": True, "value": {
            "type": "modifier", "parameters": [262144, 18446744073709289471]}},
    }
    source.write_bytes(plistlib.dumps(prefs))

    subprocess.run(["defaults", "import", str(domain), str(source)],
                   check=True, capture_output=True)
    restored = plistlib.loads(subprocess.run(
        ["defaults", "export", str(domain), "-"],
        check=True, capture_output=True,
    ).stdout)

    assert restored == prefs
    assert type(restored["AppleSymbolicHotKeys"]["15"]["enabled"]) is bool
    assert type(restored["AppleSymbolicHotKeys"]["15"]["value"]["parameters"][0]) is int
    assert restored["OtherPreference"] == 37
