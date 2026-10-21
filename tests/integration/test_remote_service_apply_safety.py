"""A routine apply never disconnects an active remote session implicitly."""
from pathlib import Path
import os
import subprocess

import pytest


@pytest.mark.skipif(os.uname().sysname != "Darwin", reason="LaunchAgent requires macOS")
@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_live_remote_service_survives_apply_by_default(profile, profile_factory, tmp_path):
    rendered = profile_factory.render(profile)
    hook = profile_factory.render_hook(
        rendered.config, profile,
        "run_after_20-ensure-desktop-commander-launch-agent.sh.tmpl", "remote-safe",
    )
    home = tmp_path / "sandbox home"
    home.mkdir()
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    for command, body in {
        "launchctl": '#!/bin/sh\nif [ "$1" = print ]; then exit 0; fi\nprintf "%s\\n" "$*" >> "$LAUNCHCTL_LOG"\n',
        "plutil": '#!/bin/sh\nexit 0\n',
    }.items():
        file = fake_bin / command
        file.write_text(body)
        file.chmod(0o755)
    live_log = tmp_path / "launchctl-mutations.txt"
    app = home / ".local/bin/desktop-commander-remote"
    app.parent.mkdir(parents=True)
    app.write_text("#!/bin/sh\nexit 0\n")
    app.chmod(0o755)
    service_dir = home / "Library/LaunchAgents"
    service_dir.mkdir(parents=True)
    plist = service_dir / "com.arthur.desktop-commander-remote.plist"
    plist.write_text("updated launchagent\n")
    marker = home / "Library/Caches/chezmoi/com.arthur.desktop-commander-remote.sha256"
    marker.parent.mkdir(parents=True)
    marker.write_text("digest of previous running service\n")
    env = {**os.environ, "HOME": str(home),
           "PATH": f"{fake_bin}:{os.environ['PATH']}",
           "LAUNCHCTL_LOG": str(live_log),
              "DOTFILES_ALLOW_SERVICE_INTERRUPTION": "0"}
    run = subprocess.run(["/bin/sh", str(hook)], env=env,
                         text=True, capture_output=True, timeout=15)
    assert run.returncode == 0, run.stderr
    assert not live_log.exists(), "live remote service must not be stopped"
    assert marker.read_text() == "digest of previous running service\n"
    assert plist.exists()


@pytest.mark.skipif(os.uname().sysname != "Darwin", reason="LaunchAgent requires macOS")
def test_service_restart_is_explicit(profile_factory, tmp_path):
    rendered = profile_factory.render("personal")
    hook = profile_factory.render_hook(
        rendered.config, "personal",
        "run_after_20-ensure-desktop-commander-launch-agent.sh.tmpl", "remote-restart",
    )
    home = tmp_path / "home"
    home.mkdir()
    app = home / ".local/bin/desktop-commander-remote"
    app.parent.mkdir(parents=True)
    app.write_text("#!/bin/sh\nexit 0\n")
    app.chmod(0o755)
    plist = home / "Library/LaunchAgents/com.arthur.desktop-commander-remote.plist"
    plist.parent.mkdir(parents=True)
    plist.write_text("new plist\n")
    commands = tmp_path / "service-actions"
    stub = tmp_path / "bin"
    stub.mkdir()
    for binary, script in {
        "launchctl": '#!/bin/sh\nif [ "$1" = print ]; then exit 0; fi\nprintf "%s\\n" "$1" >> "$LAUNCHCTL_LOG"\n',
        "plutil": '#!/bin/sh\nexit 0\n',
    }.items():
        dest = stub / binary
        dest.write_text(script)
        dest.chmod(0o755)
    run = subprocess.run(["/bin/sh", str(hook)],
                         env={**os.environ, "HOME": str(home),
                              "PATH": f"{stub}:{os.environ['PATH']}",
                              "LAUNCHCTL_LOG": str(commands),
                                                    "DOTFILES_ALLOW_SERVICE_INTERRUPTION": "1"},
                         text=True, capture_output=True, timeout=15)
    assert run.returncode == 0, run.stderr
    assert commands.read_text().splitlines() == ["bootout", "bootstrap"]
