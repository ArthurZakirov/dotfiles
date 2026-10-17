"""Exercise first-run automation without launching the developer's Hammerspoon."""

import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "home/dot_local/bin/executable_hammerspoon-verify"
HOOK = ROOT / "home/run_after_30-ensure-hammerspoon.sh"
SWIFT_SETUP = ROOT / "home/dot_local/bin/executable_hammerspoon-ensure-swiftc"


@pytest.fixture
def fake_commands(tmp_path):
    executable_dir = tmp_path / "fake-bin"
    executable_dir.mkdir()
    return executable_dir


def executable(directory, name, content):
    file = directory / name
    file.write_text("#!/bin/sh\n" + content)
    file.chmod(0o755)
    return file


@pytest.mark.parametrize(
    ("state", "success"),
    [
        (dict(accessibility=True, autolaunch=True, audio=True, hotkeys=24), True),
        (dict(accessibility=False, autolaunch=True, audio=True, hotkeys=24), False),
        (dict(accessibility=True, autolaunch=True, audio=False, hotkeys=24), False),
        (dict(accessibility=True, autolaunch=True, audio=True, hotkeys=0), False),
    ],
)
def test_runtime_verifier_reports_config_state(fake_commands, state, success):
    executable(fake_commands, "hs", 'printf "%s\\n" "$HS_TEST_RESULT"\n')
    env = {
        **os.environ, "PATH": f"{fake_commands}:{os.environ['PATH']}",
        "HS_TEST_RESULT": json.dumps(state),
    }
    result = subprocess.run([str(VERIFY)], env=env, text=True, capture_output=True)
    assert (result.returncode == 0) is success
    assert f"registered_hotkeys={state['hotkeys']}" in result.stdout
    assert f"audio_check={str(state['audio'])}" in result.stdout


def test_verifier_reports_invalid_ipc_response(fake_commands):
    executable(fake_commands, "hs", "printf 'not-json\\n'\n")
    result = subprocess.run(
        [str(VERIFY)], text=True, capture_output=True,
        env={**os.environ, "PATH": f"{fake_commands}:{os.environ['PATH']}"},
    )
    assert result.returncode != 0
    assert "invalid runtime response" in result.stderr


def test_first_run_launches_once_and_never_restarts_running_app(tmp_path, fake_commands):
    app = tmp_path / "Hammerspoon.app"
    app.mkdir()
    log = tmp_path / "calls.log"
    executable(fake_commands, "uname", "echo Darwin\n")
    executable(fake_commands, "launchctl", 'test "$1" = print\n')
    executable(
        fake_commands, "pgrep", 'test "$HAMMERSPOON_RUNNING" = 1\n'
    )
    executable(fake_commands, "open", 'echo open >> "$HAMMERSPOON_TEST_LOG"\n')
    checker = executable(
        fake_commands, "verify", 'echo verify >> "$HAMMERSPOON_TEST_LOG"\n'
    )
    setup = executable(
        fake_commands, "swift-setup", 'echo swift >> "$HAMMERSPOON_TEST_LOG"\n'
    )
    env = {
        **os.environ,
        "PATH": f"{fake_commands}:{os.environ['PATH']}",
        "HAMMERSPOON_SWIFTC_HELPER": str(setup),
        "HAMMERSPOON_APP_PATH": str(app),
        "HAMMERSPOON_VERIFY_BIN": str(checker),
        "HAMMERSPOON_TEST_LOG": str(log),
        "HAMMERSPOON_RUNNING": "0",
        "DOTFILES_SKIP_OPTIONAL_APPS": "0",
    }

    def run():
        subprocess.run(["/bin/bash", str(HOOK)], env=env, check=True)

    run()
    assert log.read_text().splitlines() == ["swift", "open", "verify"]
    env["HAMMERSPOON_RUNNING"] = "1"
    run()
    assert log.read_text().splitlines() == ["swift", "open", "verify", "swift", "verify"]

    env["DOTFILES_SKIP_OPTIONAL_APPS"] = "1"
    run()
    assert log.read_text().splitlines() == ["swift", "open", "verify", "swift", "verify"]


def test_gui_launch_skips_when_no_session(tmp_path, fake_commands):
    app = tmp_path / "Hammerspoon.app"
    app.mkdir()
    log = tmp_path / "open.log"
    executable(fake_commands, "uname", "echo Darwin\n")
    executable(fake_commands, "launchctl", "exit 1\n")
    executable(fake_commands, "open", 'echo open >> "$HAMMERSPOON_TEST_LOG"\n')
    env = {
        **os.environ, "PATH": f"{fake_commands}:{os.environ['PATH']}",
        "HAMMERSPOON_APP_PATH": str(app),
        "HAMMERSPOON_TEST_LOG": str(log),
        "DOTFILES_SKIP_OPTIONAL_APPS": "0",
    }
    subprocess.run(["/bin/bash", str(HOOK)], env=env, check=True)
    assert not log.exists()


def test_executable_and_hook_syntax():
    subprocess.run(["/bin/bash", "-n", str(HOOK)], check=True)
    assert VERIFY.read_text().startswith("#!/usr/bin/env python3")


def test_verifier_uses_bundled_cli_without_global_hs_symlink(tmp_path):
    import sys

    app = tmp_path / "Hammerspoon.app"
    bundled_dir = app / "Contents/Frameworks/hs"
    bundled_dir.mkdir(parents=True)
    args_log = tmp_path / "args"
    executable(
        bundled_dir, "hs",
        'printf "%s\\n" "$*" > "$HAMMERSPOON_TEST_LOG"\n'
        'printf "%s\\n" "$HS_TEST_RESULT"\n',
    )
    env = {
        **os.environ,
        "HAMMERSPOON_APP_PATH": str(app),
        "HAMMERSPOON_TEST_LOG": str(args_log),
        "HS_TEST_RESULT": json.dumps(
            dict(accessibility=True, autolaunch=True, audio=True, hotkeys=18)
        ),
        "PATH": "/usr/bin:/bin",
    }
    result = subprocess.run(
        [sys.executable, str(VERIFY)], env=env, text=True, capture_output=True
    )
    assert result.returncode == 0, result.stderr
    args = args_log.read_text()
    assert "-c return hs.json.encode({" in args
    assert "audio=type(HammerspoonConfig)" in args


def test_swift_toolchain_installs_only_when_compiler_missing(tmp_path, fake_commands):
    import sys

    keg = tmp_path / "swift-keg"
    install_log = tmp_path / "brew-installs"
    brew = fake_commands / "brew"
    brew.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "import sys\n"
        f"keg=Path({str(keg)!r})\n"
        f"log=Path({str(install_log)!r})\n"
        "if sys.argv[1:] == ['--prefix', 'swift']:\n"
        "    if not keg.exists(): sys.exit(1)\n"
        "    print(keg)\n"
        "elif sys.argv[1:] == ['install', 'swift']:\n"
        "    compiler=keg/'Swift-6.4.xctoolchain/usr/bin/swiftc'\n"
        "    compiler.parent.mkdir(parents=True)\n"
        "    compiler.write_text('#!/bin/sh\\nexit 0\\n')\n"
        "    compiler.chmod(0o755)\n"
        "    log.write_text('installed\\n')\n"
        "else: sys.exit(2)\n"
    )
    brew.chmod(0o755)
    env = {**os.environ, "PATH": str(fake_commands)}
    first = subprocess.run([str(SWIFT_SETUP)], env=env, text=True, capture_output=True)
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == str(keg / "Swift-6.4.xctoolchain/usr/bin/swiftc")
    assert install_log.read_text() == "installed\n"
    second = subprocess.run([str(SWIFT_SETUP)], env=env, text=True, capture_output=True)
    assert second.returncode == 0, second.stderr
    assert second.stdout == first.stdout
    assert install_log.read_text() == "installed\n"


def test_swift_setup_uses_existing_compiler_without_homebrew(tmp_path, fake_commands):
    compiler = executable(fake_commands, "swiftc", "exit 0\n")
    result = subprocess.run(
        [str(SWIFT_SETUP)],
        env={**os.environ, "PATH": str(fake_commands)},
        text=True, capture_output=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == str(compiler)


def test_lua_templates_get_lua_highlighting():
    settings = json.loads((ROOT / ".vscode/settings.json").read_text())
    assert settings["files.associations"]["**/*.lua.tmpl"] == "lua"
