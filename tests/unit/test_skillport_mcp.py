"""Read-only skill catalog and secret-bootstrap contracts."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "home/dot_local/share/skillport-mcp"


class FakeFastMCP:
    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def tool(*args, **kwargs):
        return lambda function: function


@pytest.fixture
def server(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "fastmcp", types.SimpleNamespace(FastMCP=FakeFastMCP))
    spec = importlib.util.spec_from_file_location("local_skills_mcp", SOURCE / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    installed = tmp_path / "installed"
    installed.mkdir()
    monkeypatch.setenv("SKILLPORT_SKILLS_ROOT", str(installed))
    return module, installed


def create_skill(installed, name="python-testing", description="Write Python tests."):
    # Real SkillPort may link a top-level install to a canonical Git checkout.
    canonical = installed.parent / f"canonical-{name}"
    canonical.mkdir()
    (canonical / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# Instructions\n",
        encoding="utf-8",
    )
    (installed / name).symlink_to(canonical, target_is_directory=True)
    return canonical


def test_search_and_read_installed_symlink_without_copy(server):
    service, installed = server
    canonical = create_skill(installed)
    results = service.search_skills("Python tests")
    assert results["skills"][0]["name"] == "python-testing"
    assert results["total"] == 1
    assert "# Instructions" in service.read_skill("python-testing")["instructions"]
    (canonical / "SKILL.md").write_text(
        "---\nname: python-testing\ndescription: Newly changed.\n---\n# Updated\n",
        encoding="utf-8",
    )
    assert "# Updated" in service.read_skill("python-testing")["instructions"]
    assert service.search_skills("Newly changed")["skills"][0]["description"] == "Newly changed."


def test_pagination_and_empty_catalog(server):
    service, installed = server
    assert service.search_skills("any") == {"skills": [], "total": 0, "next_offset": None}
    create_skill(installed, "python-testing")
    create_skill(installed, "software-design", "Software design guidance")
    results = service.search_skills("software design", limit=1)
    assert results["skills"][0]["name"] == "software-design"
    assert results["next_offset"] == 1
    assert service.search_skills("", limit=1, offset=1)["skills"]
    with pytest.raises(ValueError):
        service.search_skills("test", limit=0)


@pytest.mark.parametrize("name", ["../private", ".git", "python/testing", "/tmp/private"])
def test_skill_names_cannot_escape_catalog(server, name):
    service, installed = server
    create_skill(installed)
    with pytest.raises(ValueError):
        service.read_skill(name)


def test_references_must_stay_inside_selected_skill(server):
    service, installed = server
    canonical = create_skill(installed)
    (canonical / "references").mkdir()
    (canonical / "references/test.md").write_text("Safe reference")
    assert service.read_skill_resource("python-testing", "references/test.md")["content"] == "Safe reference"
    outside = installed.parent / "outside.md"
    outside.write_text("private")
    (canonical / "references/unsafe.md").symlink_to(outside)
    for path in ("../outside.md", ".env", "/tmp/other.md", "references/unsafe.md", "references/../../outside.md"):
        with pytest.raises((ValueError, FileNotFoundError)):
            service.read_skill_resource("python-testing", path)


def test_invalid_skills_do_not_break_search(server):
    service, installed = server
    create_skill(installed)
    invalid = installed / "invalid-skill"
    invalid.mkdir()
    (invalid / "SKILL.md").write_text("No frontmatter")
    assert [skill["name"] for skill in service.search_skills("anything")["skills"]] == ["python-testing"]


def test_launcher_only_injects_runtime_key(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("skillport_launcher", SOURCE / "launch.py")
    launch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launch)
    config = tmp_path / ".config/skillport-mcp"
    config.mkdir(parents=True)
    (config / "tunnel-id").write_text("tunnel_example12345678\n")
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv[0])
        if argv[0] == "security":
            return subprocess.CompletedProcess(argv, 0, "synthetic-bws-token\n", "")
        assert kwargs["env"]["BWS_ACCESS_TOKEN"] == "synthetic-bws-token"
        return subprocess.CompletedProcess(
            argv, 0,
            json.dumps([{"key": "OPENAI_TUNNEL_API_KEY", "value": "synthetic-runtime-key"}]), "",
        )

    monkeypatch.setattr(launch.subprocess, "run", fake_run)
    env, tunnel = launch.runtime_environment(tmp_path, "fake-keychain-account", {"PATH": "/bin"})
    assert tunnel == "tunnel_example12345678"
    assert env["CONTROL_PLANE_API_KEY"] == "synthetic-runtime-key"
    assert "BWS_ACCESS_TOKEN" not in env
    assert "OPENAI_TUNNEL_API_KEY" not in env
    assert calls == ["security", "bws"]


def test_configure_is_non_destructive(tmp_path):
    cli = ROOT / "home/dot_local/bin/executable_skillport-mcp-configure"
    env = {**os.environ, "HOME": str(tmp_path)}
    command = ["/bin/sh", str(cli), "tunnel_0123456789abcdef"]
    first = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    config = tmp_path / ".config/skillport-mcp/tunnel-id"
    assert config.read_text().strip() == "tunnel_0123456789abcdef"
    assert (config.stat().st_mode & 0o777) == 0o600
    second = subprocess.run(command, env=env, capture_output=True, text=True)
    assert second.returncode != 0
    assert config.read_text().strip() == "tunnel_0123456789abcdef"
    assert "already configured" in second.stderr.lower()
