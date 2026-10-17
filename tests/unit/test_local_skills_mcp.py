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
SOURCE = ROOT / "home/dot_local/share/local-skills-mcp"


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
    monkeypatch.setenv("LOCAL_SKILLS_ROOT", str(installed))
    return module, installed


def create_skill(installed, name="python-testing", description="Write Python tests."):
    # Installed skills may be directory symlinks to their source location.
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
    (canonical / "private.json").write_text('{"private": true}')
    (canonical / "references/backdoor").symlink_to(canonical, target_is_directory=True)
    for path in ("../outside.md", ".env", "/tmp/other.md", "references/unsafe.md",
                 "references/backdoor/private.json", "references/../../outside.md"):
        with pytest.raises((ValueError, FileNotFoundError)):
            service.read_skill_resource("python-testing", path)


def test_invalid_skills_do_not_break_search(server):
    service, installed = server
    create_skill(installed)
    invalid = installed / "invalid-skill"
    invalid.mkdir()
    (invalid / "SKILL.md").write_text("No frontmatter")
    assert [skill["name"] for skill in service.search_skills("anything")["skills"]] == ["python-testing"]


def test_runtime_uses_generic_secrets_and_injected_tunnel_id(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("local_skills_launcher", SOURCE / "launch.py")
    launch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launch)
    account = "account-from-chezmoi-template"
    calls = []

    def read_secrets(names, selected, inherited):
        calls.append((names, selected))
        return {
            "OPENAI_TUNNEL_API_KEY": "synthetic-runtime-key",
            "OPENAI_TUNNEL_ID": "tunnel_" + "a" * 32,
        }

    monkeypatch.setattr(launch, "credential_provider", lambda home: types.SimpleNamespace(
        read_secrets=read_secrets,
        sanitized_environment=lambda env: {k: v for k, v in env.items() if k != "BWS_ACCESS_TOKEN"},
    ))
    env, tunnel = launch.runtime_environment(tmp_path, account, {
        "PATH": "/bin", "BWS_ACCESS_TOKEN": "synthetic-legacy-token"
    })
    assert tunnel == "tunnel_" + "a" * 32
    assert env["CONTROL_PLANE_API_KEY"] == "synthetic-runtime-key"
    assert "BWS_ACCESS_TOKEN" not in env
    assert "OPENAI_TUNNEL_ID" not in env
    assert calls == [({"OPENAI_TUNNEL_ID", "OPENAI_TUNNEL_API_KEY"}, account)]


def test_machine_local_tunnel_config_overrides_secrets(tmp_path):
    spec = importlib.util.spec_from_file_location("local_skills_launcher", SOURCE / "launch.py")
    launch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launch)
    path = tmp_path / ".config/local-skills-mcp/tunnel-id"
    path.parent.mkdir(parents=True)
    path.write_text("tunnel_" + "b" * 32 + "\n")
    assert launch.select_tunnel_id(tmp_path, {"OPENAI_TUNNEL_ID": "tunnel_" + "a" * 32}) == "tunnel_" + "b" * 32


@pytest.mark.parametrize("invalid", ["tunnel_short", "tunnel_" + "F" * 32, "../secret"])
def test_rejects_invalid_tunnel_id(tmp_path, invalid):
    spec = importlib.util.spec_from_file_location("local_skills_launcher", SOURCE / "launch.py")
    launch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launch)
    with pytest.raises(ValueError):
        launch.select_tunnel_id(tmp_path, {"OPENAI_TUNNEL_ID": invalid})


def test_unrelated_skill_files_are_not_readable(server):
    service, installed = server
    canonical = create_skill(installed)
    (canonical / "config.json").write_text('{"private": true}')
    with pytest.raises(ValueError):
        service.read_skill_resource("python-testing", "config.json")
