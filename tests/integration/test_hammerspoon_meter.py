"""Executable microphone meter: compilation, caching, and rebuild recovery."""

import os
from pathlib import Path
import shutil
import subprocess

METER = Path(__file__).resolve().parents[2] / "home/dot_hammerspoon/bin/executable_mic_level"


def test_meter_compiles_once_and_recovers_after_failed_rebuild(tmp_path):
    source_dir = tmp_path / "hammerspoon/bin"
    source_dir.mkdir(parents=True)
    shutil.copy2(METER, source_dir / "mic_level")
    shutil.copy2(METER.parent / "mic_level.swift", source_dir / "mic_level.swift")
    compiler_bin = tmp_path / "fake-bin"
    compiler_bin.mkdir()
    compiler = compiler_bin / "swiftc"
    log = tmp_path / "compiler-calls"
    fake_executable = tmp_path / "fake-executable"
    fake_executable.write_text("#!/bin/sh\necho mic-value\n")
    fake_executable.chmod(0o755)
    compiler.write_text(
        "#!/bin/sh\n"
        'echo build >> "$SWIFTC_LOG"\n'
        'cp "$MIC_FAKE_EXE" "$3"\n'
    )
    compiler.chmod(0o755)
    env = {
        **os.environ, "HOME": str(tmp_path),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "PATH": f"{compiler_bin}:{os.environ['PATH']}",
        "SWIFTC_LOG": str(log),
        "MIC_FAKE_EXE": str(fake_executable),
    }

    meter = source_dir / "mic_level"
    first = subprocess.run([str(meter)], env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == "mic-value"
    assert subprocess.run([str(meter)], env=env, capture_output=True).returncode == 0
    assert log.read_text().splitlines() == ["build"]

    # A failed rebuild must keep the last working cached binary.
    compiled = tmp_path / "cache/hammerspoon/mic_level"
    source = source_dir / "mic_level.swift"
    os.utime(source, (compiled.stat().st_mtime + 5,) * 2)
    compiler.write_text("#!/bin/sh\nexit 17\n")
    assert subprocess.run([str(meter)], env=env, capture_output=True).returncode == 17
    assert compiled.exists() and os.access(compiled, os.X_OK)
    compiler.write_text(
        "#!/bin/sh\n"
        'echo build >> "$SWIFTC_LOG"\n'
        'cp "$MIC_FAKE_EXE" "$3"\n'
    )
    assert subprocess.run([str(meter)], env=env, capture_output=True).returncode == 0
    assert log.read_text().splitlines() == ["build", "build"]
