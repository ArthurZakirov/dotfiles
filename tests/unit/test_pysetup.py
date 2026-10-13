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
    """Validate supported Poetry syntax conversion."""
    assert pysetup.python_spec(constraint) == expected


@pytest.mark.parametrize("constraint", ["^", "3.12 || 3.13", "python3", {"version": "^3.11"}])
def test_reject_unsupported_constraints(constraint):
    """Reject incompatible Poetry version expressions."""
    with pytest.raises(pysetup.SetupError, match="Unsupported"):
        pysetup.python_spec(constraint)


@pytest.mark.parametrize("url", [
    "https://username:password@example.org/private.whl",
    "https://example.org/a.whl?token=secret",
    "https://example.org/a.whl#sha256=secret",
])
def test_export_rejects_credential_capable_urls(tmp_path, url):
    """Never accept potentially credential-bearing requirement URLs."""
    exported = tmp_path / "requirements.txt"
    exported.write_text(url + "\n")
    with pytest.raises(pysetup.SetupError, match="credential-capable"):
        pysetup.safe_export(exported)


def test_safe_export_allows_pinned_public_requirement(tmp_path):
    """Accept hashed public packages."""
    exported = tmp_path / "requirements.txt"
    exported.write_text("example==1.2.3 --hash=sha256:" + "0" * 64 + "\n")
    pysetup.safe_export(exported)


def test_environment_creation_uses_uv_and_pins_lower_series(monkeypatch, tmp_path):
    """Prefer a compatible concrete Python minor version."""
    recorded = []
    monkeypatch.setattr(pysetup, "run", lambda args, label, cwd: recorded.append((args, label, cwd)))
    pysetup.create_environment(">=3.11,<4", tmp_path / ".venv", tmp_path)
    args, label, cwd = recorded[0]
    assert args[:5] == ["uv", "venv", "--no-project", "--python", ">=3.11,<4,==3.11.*"]
    assert label == "Environment creation"
    assert cwd == tmp_path


def test_failed_subprocess_does_not_leak_authentication_details(monkeypatch, tmp_path):
    """Avoid emitting potentially sensitive subprocess output."""
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 1, b"", b"HTTP 401 token=private")
    monkeypatch.setattr(pysetup.subprocess, "run", fake_run)
    with pytest.raises(pysetup.SetupError) as error:
        pysetup.run(["uv", "pip", "sync"], "Locked dependency sync", tmp_path)
    assert "authentication failed" in str(error.value)
    assert "private" not in str(error.value)


def test_missing_manifest_exits_without_creating_files(tmp_path):
    """Reject missing project metadata without side effects."""
    result = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)],
                            text=True, capture_output=True)
    assert result.returncode == 1
    assert "both pyproject.toml and poetry.lock" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_major_only_constraint_does_not_pin_python_3_0(monkeypatch, tmp_path):
    """A broad caret range must allow a modern Python interpreter."""
    calls = []
    monkeypatch.setattr(pysetup, "run", lambda args, *rest: calls.append(args))
    pysetup.create_environment(pysetup.python_spec("^3"), tmp_path / ".venv", tmp_path)
    assert calls[0][4] == ">=3.0.0,<4.0.0"
    assert "==3.0.*" not in calls[0][4]


def test_poetry_python_range_takes_precedence(tmp_path, monkeypatch):
    """The lock's Poetry range must override broader package metadata."""
    import hashlib
    project = tmp_path / "project"
    project.mkdir()
    manifest = ('[project]\nrequires-python = ">=3.8"\n'
                '[tool.poetry.dependencies]\npython = ">=3.11,<4"\n')
    (project / "pyproject.toml").write_text(manifest)
    (project / "poetry.lock").write_text("fake lock")
    home = tmp_path / "home"
    cache = home / "Library/Caches/pysetup"
    cache.mkdir(parents=True)
    key = hashlib.sha256(pysetup.CACHE_VERSION + b"\0" + manifest.encode() + b"\0" + b"fake lock").hexdigest()
    (cache / (key + ".requirements.txt")).write_text("")
    monkeypatch.setattr(pysetup.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(pysetup.sys, "argv", ["pysetup", str(project)])
    monkeypatch.setattr(pysetup, "UV", str(tmp_path / "uv"))
    (tmp_path / "uv").write_text("stub")
    calls = []
    def record(args, label, cwd, report=True):
        calls.append(args)
        if label == "Interpreter check":
            return b'["/wrong", "/base", "3.11.1"]'
        return b""
    monkeypatch.setattr(pysetup, "run", record)
    with pytest.raises(pysetup.SetupError):
        pysetup.main()
    assert next(x for x in calls if x[1] == "venv")[4].startswith(">=3.11,<4")


def test_fake_venv_interpreter_rejected_before_sync(tmp_path, monkeypatch):
    """Reject a base Python symlink disguised as a project interpreter."""
    environment = tmp_path / ".venv"
    (environment / "bin").mkdir(parents=True)
    (environment / "pyvenv.cfg").write_text("home = /base\n")
    (environment / "bin/python").symlink_to(sys.executable)
    monkeypatch.setattr(pysetup, "run", lambda *a, **k: b'["/base", "/base", "3.11.1"]')
    with pytest.raises(pysetup.SetupError, match="not isolated"):
        pysetup.verify_environment(environment / "bin/python", environment, tmp_path)


@pytest.mark.parametrize("invalid_output", [b"not json", b"{}", b"[]", b"[1, 2, 3]", b"null"])
def test_invalid_interpreter_metadata_is_reported_without_sync(monkeypatch, tmp_path, invalid_output):
    """Malformed interpreter output cannot proceed to dependency synchronization."""
    environment = tmp_path / ".venv"
    (environment / "bin").mkdir(parents=True)
    (environment / "pyvenv.cfg").write_text("home = /base\n")
    (environment / "bin/python").symlink_to(sys.executable)
    calls = []
    def fake_run(args, label, cwd, report=True):
        calls.append(label)
        return invalid_output
    monkeypatch.setattr(pysetup, "run", fake_run)
    with pytest.raises(pysetup.SetupError, match="invalid interpreter metadata.*preserved"):
        pysetup.verify_environment(environment / "bin/python", environment, tmp_path)
    assert calls == ["Interpreter check"]
