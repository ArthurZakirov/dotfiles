"""End-to-end Codex Voice provisioning with real chezmoi and an isolated HOME.

Fast tests exercise managed executables and the launcher without a network call.
Opt in to the real, pinned GitHub Release test on macOS with
RUN_CODEX_VOICE_SYSTEM_E2E=1; never provision the developer's actual HOME.
"""

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "home"
LAUNCHER = Path(".local/bin/codex-voice")
INSTALLER = Path(".local/bin/codex-voice-install")
HOOK = Path("run_after_45-install-codex-voice.sh.tmpl")
PACKAGE = Path(".local/share/codex-voice")


def command(*args: str, env: dict[str, str], timeout: int = 45) -> str:
    result = subprocess.run(
        args, env=env, check=False, capture_output=True, text=True, timeout=timeout
    )
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result.stdout


@pytest.fixture
def isolated_voice(tmp_path: Path) -> tuple[Path, dict[str, str], str, str]:
    # Only feature-owned sources: no unrelated install hooks, LaunchAgents or
    # developer settings can be applied by this test.
    source = tmp_path / "source"
    home = tmp_path / "home"
    source.mkdir()
    home.mkdir()
    legacy = home / ".local/share/codex-voice-experiment"
    legacy.mkdir(parents=True)
    (legacy / "keep-me.txt").write_text("previous-build")
    for relative in (LAUNCHER, INSTALLER, HOOK):
        target = source / (
            Path("dot_local/bin") / relative.name
            if relative in (LAUNCHER, INSTALLER)
            else relative
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        original = SOURCE / (
            Path("dot_local/bin") / ("executable_" + relative.name)
            if relative in (LAUNCHER, INSTALLER)
            else relative
        )
        if relative in (LAUNCHER, INSTALLER):
            target = target.with_name("executable_" + target.name)
        shutil.copy2(original, target)

    metadata = (SOURCE / ".chezmoidata.toml").read_text()
    assert "[codexVoice]" in metadata
    # The committed defaults must provision the release on a new machine.
    assert '    enabled = true\n    tag = "voice-v0.166.0-r4"' in metadata
    (source / ".chezmoidata.toml").write_text(metadata)

    config = tmp_path / "chezmoi.toml"
    config.write_text("")
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{home / '.local/bin'}:{os.environ['PATH']}",
    }
    base = [
        "chezmoi", "--source", str(source), "--config", str(config),
        "--destination", str(home),
    ]
    hook = command(
        *base, "execute-template", "--file", str(source / HOOK), env=env
    )
    command("bash", "-n", "-c", hook, env=env)
    assert "--release-tag" in hook
    assert "voice-v0.166.0-r4" in hook
    return home, env, hook, "voice-v0.166.0-r4"


def test_chezmoi_launcher_forwards_flags_and_sets_verbatim_speech(
    isolated_voice: tuple[Path, dict[str, str], str, str],
) -> None:
    home, env, _, _ = isolated_voice
    base = [
        "chezmoi", "--source", str(home.parent / "source"),
        "--config", str(home.parent / "chezmoi.toml"),
        "--destination", str(home),
    ]
    command(*base, "apply", "--exclude", "scripts", "--force", env=env)
    for relative in (LAUNCHER, INSTALLER):
        assert (home / relative).is_file()
        assert os.access(home / relative, os.X_OK)
    binary = home / PACKAGE / "bin/codex"
    binary.parent.mkdir(parents=True)
    binary.write_text(
        '#!/bin/sh\nprintf "%s:%s\\n" "$CODEX_REALTIME_VERBATIM_SPEECH" "$*"\n'
    )
    binary.chmod(0o755)

    output = command(str(home / LAUNCHER), "--no-daemon", env=env)

    assert output.strip() == "1:--no-daemon"
    assert (home / ".local/share/codex-voice-experiment/keep-me.txt").read_text() == "previous-build"


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_one_apply_installs_missing_voice_and_reuses_existing_voice(
    isolated_voice: tuple[Path, dict[str, str], str, str],
    profile: str,
) -> None:
    home, env, _, tag = isolated_voice
    (home.parent / "chezmoi.toml").write_text(
        f'[data]\nprofile = "{profile}"\n'
    )
    # Stub only the network/package boundary. Real chezmoi applies the source,
    # installs the launcher and executes the actual run_after template.
    installer = home.parent / "source/dot_local/bin/executable_codex-voice-install"
    installer.write_text(
        """#!/usr/bin/env python3
import os
from pathlib import Path
import sys

assert sys.argv[1:] == ["--release-tag", "voice-v0.166.0-r4"]
home = Path(os.environ["HOME"])
destination = home / ".local/share/codex-voice"
executable = destination / "bin/codex"
log = home / ".local/share/codex-voice-install-calls"
log.parent.mkdir(parents=True, exist_ok=True)
with log.open("a") as output:
    output.write("reused\\n" if executable.is_file() else "installed\\n")
if not executable.is_file():
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text('#!/bin/sh\\necho codex-cli 0.166.0\\n')
    executable.chmod(0o755)
"""
    )
    base = [
        "chezmoi", "--source", str(home.parent / "source"),
        "--config", str(home.parent / "chezmoi.toml"),
        "--destination", str(home),
    ]
    # First invocation starts from an empty managed HOME, not a pre-applied one.
    command(*base, "apply", "--force", env=env)
    binary = home / PACKAGE / "bin/codex"
    assert binary.is_file()
    assert "codex-cli 0.166.0" in command(
        str(home / LAUNCHER), "--version", env=env
    )
    assert (home / ".local/share/codex-voice-install-calls").read_text() == "installed\n"

    # Subsequent applies execute the same hook but do not reinstall the binary.
    command(*base, "apply", "--force", env=env)
    assert (home / ".local/share/codex-voice-install-calls").read_text() == (
        "installed\nreused\n"
    )
    assert (home / ".local/share/codex-voice-experiment/keep-me.txt").read_text() == (
        "previous-build"
    )


@pytest.mark.skipif(
    platform.system() != "Darwin"
    or os.environ.get("RUN_CODEX_VOICE_SYSTEM_E2E") != "1",
    reason="Opt-in real macOS GitHub release test (no live HOME or CI download)",
)
def test_chezmoi_installs_pinned_release_and_launches_real_cli(
    isolated_voice: tuple[Path, dict[str, str], str, str],
) -> None:
    home, env, hook, tag = isolated_voice

    # One real chezmoi apply must install files AND execute the after-hook.
    base = [
        "chezmoi", "--source", str(home.parent / "source"),
        "--config", str(home.parent / "chezmoi.toml"),
        "--destination", str(home),
    ]
    output = command(*base, "apply", "--force", "--verbose", env=env, timeout=240)
    assert f"Installed Codex Voice {tag}" in output
    for relative in (LAUNCHER, INSTALLER):
        assert (home / relative).is_file()
        assert os.access(home / relative, os.X_OK)

    receipt = json.loads((home / PACKAGE / "codex-voice-install.json").read_text())
    voice = home / PACKAGE / "codex-resources/voice"
    manifest = json.loads((voice / "manifest.json").read_text())
    assert receipt["tag"] == tag
    cpu = {"arm64": "aarch64", "x86_64": "x86_64"}[platform.machine()]
    expected_target = f"{cpu}-apple-darwin"
    assert receipt["target"] == manifest["appTarget"] == expected_target
    assert receipt["build_commit"] == manifest["buildCommit"]
    assert len(manifest["sha256"]) > 0

    launcher = str(home / LAUNCHER)
    assert "codex-cli 0.166.0" in command(launcher, "--version", env=env)
    assert "Usage:" in command(launcher, "--no-daemon", "--help", env=env)
    helper = voice / "bin/codex-voice-host"
    assert command(str(helper), "--build-commit", env=env).strip() == receipt["build_commit"]
    command("codesign", "--verify", str(helper), env=env)

    # Keep the separately maintained experimental fork untouched.
    assert (home / ".local/share/codex-voice-experiment/keep-me.txt").read_text() == "previous-build"

    # A repeated apply must verify and reuse the package, not download it.
    initial_receipt = (home / PACKAGE / "codex-voice-install.json").read_bytes()
    second = command(*base, "apply", "--force", "--verbose", env=env, timeout=90)
    assert f"Codex Voice already installed: {tag}" in second
    assert (home / PACKAGE / "codex-voice-install.json").read_bytes() == initial_receipt
    assert not list((home / PACKAGE).parent.glob("codex-voice.backup-*"))
