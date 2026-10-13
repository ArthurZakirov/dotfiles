"""Unit coverage for the Poetry-lock virtual environment helper."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "home/dot_local/bin/executable_pysetup"
loader = SourceFileLoader("pysetup", str(SCRIPT))
spec = spec_from_loader(loader.name, loader)
pysetup = module_from_spec(spec)
loader.exec_module(pysetup)


@pytest.mark.parametrize(("constraint", "expected"), [
    ("^3.11", ">=3.11.0,<4.0.0"),
    ("~3.11", ">=3.11.0,<3.12.0"),
    ("~=3.11", "~=3.11"),
    (">=3.11,<3.14", ">=3.11,<3.14"),
    ("3.12.*", "==3.12.*"),
    ("*", ">=3"),
])
def test_python_spec(constraint, expected):
    assert pysetup.python_spec(constraint) == expected


@pytest.mark.parametrize("constraint", ["^", "3.12 || 3.13", "python3", {"version": "^3.11"}])
def test_reject_unsupported_constraints(constraint):
    with pytest.raises(pysetup.SetupError, match="Unsupported"):
        pysetup.python_spec(constraint)


@pytest.mark.parametrize("url", [
    "https://username:password@example.org/private.whl",
    "https://example.org/a.whl?token=secret",
    "https://example.org/a.whl#sha256=secret",
])
def test_export_rejects_credential_capable_urls(tmp_path, url):
    exported = tmp_path / "requirements.txt"
    exported.write_text(url + "\n")
    with pytest.raises(pysetup.SetupError, match="credential-capable"):
        pysetup.safe_export(exported)


def test_safe_export_allows_pinned_public_requirement(tmp_path):
    exported = tmp_path / "requirements.txt"
    exported.write_text("example==1.2.3 --hash=sha256:" + "0" * 64 + "\n")
    pysetup.safe_export(exported)


def test_environment_creation_uses_uv_and_pins_lower_series(monkeypatch, tmp_path):
    recorded = []
    monkeypatch.setattr(pysetup, "run", lambda args, label, cwd: recorded.append((args, label, cwd)))
    pysetup.create_environment(">=3.11,<4", tmp_path / ".venv", tmp_path)
    args, label, cwd = recorded[0]
    assert args[:5] == ["uv", "venv", "--no-project", "--python", ">=3.11,<4,==3.11.*"]
    assert label == "Environment creation"
    assert cwd == tmp_path


def test_failed_subprocess_does_not_leak_authentication_details(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 1, b"", b"HTTP 401 token=private")
    monkeypatch.setattr(pysetup.subprocess, "run", fake_run)
    with pytest.raises(pysetup.SetupError) as error:
        pysetup.run(["uv", "pip", "sync"], "Locked dependency sync", tmp_path)
    assert "authentication failed" in str(error.value)
    assert "private" not in str(error.value)


def test_missing_manifest_exits_without_creating_files(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)],
                            text=True, capture_output=True)
    assert result.returncode == 1
    assert "both pyproject.toml and poetry.lock" in result.stderr
    assert list(tmp_path.iterdir()) == []
