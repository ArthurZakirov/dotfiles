"""Shared Hammerspoon configuration rendered through real chezmoi."""

from pathlib import Path

import pytest


@pytest.mark.parametrize("profile", ("personal", "professional"))
def test_full_hammerspoon_configuration_is_shared_across_profiles(profile, profile_factory):
    rendered = profile_factory.render(profile)
    managed = set(profile_factory.chezmoi(
        rendered.config, "managed", "--include", "files"
    ).splitlines())

    assert ".hammerspoon/init.lua" in managed
    assert ".hammerspoon/modules/displays.lua" in managed
    assert ".hammerspoon/modules/claude.lua" in managed

    audio_files = {
        ".hammerspoon/modules/audio_check.lua",
        ".hammerspoon/bin/mic_level",
        ".hammerspoon/bin/mic_level.swift",
    }
    assert audio_files <= managed


def test_both_profiles_generate_identical_hammerspoon_files(profile_factory):
    configurations = {
        profile: profile_factory.render(profile).config
        for profile in ("personal", "professional")
    }
    tree = {}
    for profile, config in configurations.items():
        managed = profile_factory.chezmoi(
            config, "managed", "--include", "files"
        ).splitlines()
        paths = [path for path in managed if path.startswith(".hammerspoon/")]
        tree[profile] = {
            path: profile_factory.chezmoi(
                config, "cat", str(Path.home() / path)
            )
            for path in paths
        }
        assert ".hammerspoon/modules/audio_check.lua" in tree[profile]
        scripts = profile_factory.chezmoi(config, "managed", "--include", "scripts")
        assert "30-ensure-hammerspoon.sh" in scripts

    assert tree["personal"] == tree["professional"]
