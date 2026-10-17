"""Hammerspoon Swift toolchain provisioning CLI behavior."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.support.hammerspoon_process import executable

SWIFT_SETUP = Path(__file__).resolve().parents[2] / "home/dot_local/bin/executable_hammerspoon-ensure-swiftc"


@pytest.fixture
def fake_commands(tmp_path):
    directory = tmp_path / "fake-bin"
    directory.mkdir()
    return directory


def test_swift_toolchain_installs_only_when_compiler_missing(tmp_path, fake_commands):
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
