"""Integration and executable E2E checks in disposable homes and checkouts."""
import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "home/dot_local/bin/executable_pysetup"


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_chezmoi_renders_executable_pysetup(profile, profile_factory):
    """Verify both chezmoi profiles render the same executable."""
    rendered = profile_factory.render(profile)
    output = profile_factory.chezmoi(rendered.config, "cat", str(Path.home() / ".local/bin/pysetup"))
    assert output == SCRIPT.read_text()
    assert "uv pip sync" not in output  # executable invokes subprocess argument vectors


def test_pysetup_real_uv_setup_reuse_and_lock_cache(tmp_path):
    """Use actual uv venv and pip commands; stub ONLY Poetry export to avoid network."""
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv is not installed on this host")
    series = f"{sys.version_info.major}.{sys.version_info.minor}"
    available = subprocess.run([uv, "python", "find", "--no-python-downloads", series],
                               capture_output=True)
    if available.returncode:
        pytest.skip(f"Python {series} is not installed for uv")
    project = tmp_path / "checkout"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[tool.poetry]\npackage-mode = false\n'
        f'[tool.poetry.dependencies]\npython = ">={series},<4.0"\n'
    )
    (project / "poetry.lock").write_text("synthetic lock for intercepted export\n")
    (project / ".gitignore").write_text(".venv/\n")
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    home = tmp_path / "home"
    home.mkdir()
    bin_path = tmp_path / "bin"
    bin_path.mkdir()
    fake_uv = bin_path / "uv"
    fake_uv.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = "tool" ]; then\n'
        '  case " $* " in\n'
        '    *" check --lock "*) exit 0;;\n'
        '    *" export "*)\n'
        '      prev=""; for arg in "$@"; do\n'
        '        if [ "$prev" = "-o" ]; then : > "$arg"; exit 0; fi\n'
        '        prev="$arg";\n'
        '      done; exit 1;;\n'
        '  esac\n'
        '  exit 2\n'
        'fi\n'
        'if [ "$1" = "venv" ]; then exec "' + uv + '" "$@" --no-python-downloads; fi\n'
        'exec "' + uv + '" "$@"\n'
    )
    fake_uv.chmod(0o755)
    env = {**os.environ, "HOME": str(home), "PATH": str(bin_path) + os.pathsep + os.environ["PATH"],
           "UV_PYTHON_DOWNLOADS": "never", "UV_NO_PROGRESS": "1"}
    # Real tool resolution uses PATH at import time. Protect network by using installed interpreter.
    def execute():
        return subprocess.run([sys.executable, str(SCRIPT), str(project)],
                              env=env, text=True, capture_output=True, timeout=90)
    first = execute()
    assert first.returncode == 0, first.stderr + first.stdout
    interpreter = project / ".venv/bin/python"
    assert interpreter.is_file()
    assert subprocess.run([str(interpreter), "-c", "import sys; assert sys.prefix != sys.base_prefix"]).returncode == 0
    assert "Environment creation" in first.stdout
    second = execute()
    assert second.returncode == 0, second.stderr + second.stdout
    assert "Environment: reused" in second.stdout
    assert "Lock export: cached" in second.stdout
    assert len(list((home / "Library/Caches/pysetup").glob("*.requirements.txt"))) == 1
    assert ".venv/" not in (project / ".git/info/exclude").read_text()


def test_pysetup_preserves_invalid_existing_venv(tmp_path):
    """Reject damaged existing environments without modifying them."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text('[tool.poetry.dependencies]\npython = "^3.11"\n')
    (project / "poetry.lock").write_text("fake")
    venv = project / ".venv"
    venv.mkdir()
    marker = venv / "user-data"
    marker.write_text("preserve")
    # Prepopulate the exact export cache so no Poetry network access is needed.
    home = tmp_path / "home"
    cache = home / "Library/Caches/pysetup"
    cache.mkdir(parents=True)
    key = hashlib.sha256(
        b"pysetup-v1:poetry-2.4.1:export-1.10.1:all-groups:hashes" + b"\0"
        + (project / "pyproject.toml").read_bytes() + b"\0"
        + (project / "poetry.lock").read_bytes()
    ).hexdigest()
    (cache / (key + ".requirements.txt")).write_text("")
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    uv_stub = stub_dir / "uv"
    uv_stub.write_text('#!/bin/sh\nexit 99\n')
    uv_stub.chmod(0o755)
    result = subprocess.run([sys.executable, str(SCRIPT), str(project)],
                            env={**os.environ, "HOME": str(home),
                                 "PATH": str(stub_dir) + os.pathsep + os.environ["PATH"]},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert "Existing .venv is not a usable Python environment" in result.stderr
    assert marker.read_text() == "preserve"
