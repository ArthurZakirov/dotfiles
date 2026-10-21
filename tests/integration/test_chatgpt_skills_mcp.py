"""Real stdio MCP discovery and isolated chezmoi/launchd lifecycle tests."""

import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "home/dot_local/share/local-skills-mcp"
LABEL = "local.skills.mcp"


@pytest.mark.skipif(not (APP / ".venv/bin/python").exists(), reason="Run uv sync for real MCP protocol tests")
def test_client_discovers_and_reads_live_skills_over_stdio(tmp_path):
    """Exercise real MCP initialize, tools/list and tools/call at the public boundary."""
    installed = tmp_path / "installed"
    installed.mkdir()
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "SKILL.md").write_text(
        "---\nname: python-testing\ndescription: Python testing\n---\nOriginal instructions\n"
    )
    (canonical / "references").mkdir()
    (canonical / "references/test.md").write_text("Live reference")
    (installed / "python-testing").symlink_to(canonical, target_is_directory=True)
    code = r'''
import asyncio
import os
import sys
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

async def main():
    transport = StdioTransport(
        command=sys.executable, args=[sys.argv[1]],
        env={"LOCAL_SKILLS_ROOT": sys.argv[2]},
    )
    async with Client(transport) as client:
        names = {tool.name for tool in await client.list_tools()}
        assert names == {"search_skills", "read_skill", "read_skill_resource"}
        search = await client.call_tool("search_skills", {"query": "Python tests"})
        assert search.data["skills"][0]["name"] == "python-testing"
        original = await client.call_tool("read_skill", {"name": "python-testing"})
        assert "Original instructions" in original.data["instructions"]
        from pathlib import Path
        Path(sys.argv[3]).write_text(chr(10).join([
            "---", "name: python-testing", "description: updated", "---",
            "Updated instructions", "",
        ]))
        changed = await client.call_tool("read_skill", {"name": "python-testing"})
        assert "Updated instructions" in changed.data["instructions"]
        reference = await client.call_tool(
            "read_skill_resource", {"name": "python-testing", "path": "references/test.md"}
        )
        assert reference.data["content"] == "Live reference"
        escaping = await client.call_tool(
            "read_skill_resource", {"name": "python-testing", "path": "../outside.md"}, raise_on_error=False
        )
        assert escaping.is_error
asyncio.run(main())
'''
    proc = subprocess.run(
        [str(APP / ".venv/bin/python"), "-c", code,
         str(APP / "server.py"), str(installed), str(canonical / "SKILL.md")],
        text=True, capture_output=True, timeout=45,
    )
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("profile,expected", [("personal", True), ("professional", False)])
def test_chezmoi_scopes_mcp_integration_to_personal(profile, expected, profile_factory):
    rendered = profile_factory.render(profile)
    managed = profile_factory.chezmoi(
        rendered.config, "managed", "--include", "files"
    ).splitlines()
    assert (f"Library/LaunchAgents/{LABEL}.plist" in managed) is expected
    assert (".local/bin/local-skills-mcp-launch" in managed) is expected
    assert (".local/share/local-skills-mcp/server.py" in managed) is expected
    assert (".local/share/dotfiles-secrets/secret_store.py" in managed) is expected
    assert not any("/.venv/" in path for path in managed)
    hook = profile_factory.render_hook(
        rendered.config, profile, "run_after_25-ensure-local-skills-mcp.sh.tmpl", "mcp"
    )
    subprocess.run(["/bin/sh", "-n", str(hook)], check=True)


def test_unchosen_tunnel_does_not_start_or_install_dependencies(tmp_path, profile_factory):
    rendered = profile_factory.render("personal")
    home = tmp_path / "home"
    home.mkdir()
    hook = profile_factory.render_hook(
        rendered.config, "personal", "run_after_25-ensure-local-skills-mcp.sh.tmpl", "mcp"
    )
    result = subprocess.run(
        ["/bin/sh", str(hook)],
        env={**os.environ, "HOME": str(home)},
        text=True, capture_output=True, timeout=15,
    )
    assert result.returncode == 0
    assert not (home / ".local/state/local-skills-mcp").exists()

@pytest.fixture
def isolated_agent(tmp_path, profile_factory):
    """Exercise the real rendered hook without touching this Mac's launchd."""
    rendered = profile_factory.render("personal")
    home = tmp_path / "home"
    home.mkdir()
    apply = subprocess.run(
        ["chezmoi", "--source", str(ROOT / "home"), "--config", str(rendered.config),
         "--destination", str(home), "apply", "--exclude", "scripts", "--force"],
        text=True, capture_output=True, timeout=40,
    )
    assert apply.returncode == 0, apply.stderr
    config = home / ".config/local-skills-mcp"
    config.mkdir(parents=True)
    (config / "tunnel-id").write_text("tunnel_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
    hook = profile_factory.render_hook(
        rendered.config, "personal", "run_after_25-ensure-local-skills-mcp.sh.tmpl", "launchd"
    )
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    for name, script in {
        "uv": """#!/bin/sh
mkdir -p "$HOME/.local/share/local-skills-mcp/.venv/bin"
touch "$HOME/.local/share/local-skills-mcp/.venv/bin/python"
chmod +x "$HOME/.local/share/local-skills-mcp/.venv/bin/python"
""",
        "tunnel-client": "#!/bin/sh\nexit 0\n",
        "bws": """#!/bin/sh
if [ -f "${TEST_BWS_FAILURE:-/nonexistent}" ]; then
  echo 'simulated backend failure' >&2
  exit 2
fi
if [ -n "${TEST_BWS_ID:-}" ]; then
  printf '[{"key":"OPENAI_TUNNEL_API_KEY","value":"synthetic-runtime-key"},{"key":"OPENAI_TUNNEL_ID","value":"%s"}]\\n' "$TEST_BWS_ID"
else
  printf '[{"key":"OPENAI_TUNNEL_API_KEY","value":"synthetic-runtime-key"}]\\n'
fi
""",
        "security": "#!/bin/sh\necho synthetic-bws-token\n",
        "pgrep": """#!/bin/sh
[ -f "$TEST_DEMO_RUNNING" ] || exit 1
echo 424242
""",
        "ps": """#!/bin/sh
echo "tunnel-client run --control-plane.tunnel-id tunnel_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
""",
        "launchctl": """#!/bin/sh
echo "$*" >> "$TEST_SERVICE_CALLS"
case "$1" in
    print)
      case "$2" in
        *local.skills.mcp) [ -f "$TEST_SERVICE_RUNNING" ];;
        *skillport-mcp) [ -f "$TEST_LEGACY_SERVICE_RUNNING" ];;
        *) exit 1;;
      esac ;;
    bootstrap)
      if [ -f "${TEST_FAIL_BOOTSTRAP:-/nonexistent}" ] &&
         [ "$3" = "$HOME/Library/LaunchAgents/local.skills.mcp.plist" ]; then
        exit 1
      fi
      case "$*" in
        *last-working.plist*) touch "$TEST_SERVICE_RUNNING";;
        *local.skills.mcp*) touch "$TEST_SERVICE_RUNNING";;
        *skillport-mcp*) touch "$TEST_LEGACY_SERVICE_RUNNING";;
      esac ;;
    bootout)
      case "$*" in
        *local.skills.mcp*) rm -f "$TEST_SERVICE_RUNNING";;
        *skillport-mcp*) rm -f "$TEST_LEGACY_SERVICE_RUNNING";;
      esac ;;
    *) exit 2;;
esac
""",
    }.items():
        path = fakebin / name
        path.write_text(script)
        path.chmod(0o755)
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{fakebin}:{os.environ['PATH']}",
        "TEST_DEMO_RUNNING": str(tmp_path / "demo-running"),
        "TEST_SERVICE_RUNNING": str(tmp_path / "service-running"),
        "TEST_LEGACY_SERVICE_RUNNING": str(tmp_path / "legacy-service-running"),
        "TEST_SERVICE_CALLS": str(tmp_path / "service-calls"),
        "TEST_BWS_FAILURE": str(tmp_path / "backend-failure"),
        "TEST_FAIL_BOOTSTRAP": str(tmp_path / "bootstrap-failure"),
    }

    def run():
        return subprocess.run(["/bin/sh", str(hook)], env=env,
                              text=True, capture_output=True, timeout=25)

    def calls():
        path = Path(env["TEST_SERVICE_CALLS"])
        return path.read_text().splitlines() if path.exists() else []

    return home, env, run, calls


def test_chezmoi_apply_runs_launchagent_setup_automatically(
    isolated_agent, profile_factory, tmp_path
):
    """A normal chezmoi apply invokes the managed after-hook without manual launchctl."""
    home, env, _, calls = isolated_agent
    source = tmp_path / "hook-source"
    source.mkdir()
    script = source / "run_after_25-ensure-local-skills-mcp.sh"
    personal = profile_factory.render("personal")
    rendered = profile_factory.render_hook(
        personal.config, "personal", "run_after_25-ensure-local-skills-mcp.sh.tmpl", "apply"
    )
    script.write_text(rendered.read_text())
    script.chmod(0o755)

    command = ["chezmoi", "--source", str(source), "--destination", str(home), "apply"]
    first = subprocess.run(command, env=env, text=True, capture_output=True, timeout=25)
    assert first.returncode == 0, first.stderr
    assert sum(call.startswith("bootstrap ") for call in calls()) == 1

    repeat = subprocess.run(command, env=env, text=True, capture_output=True, timeout=25)
    assert repeat.returncode == 0, repeat.stderr
    assert sum(call.startswith("bootstrap ") for call in calls()) == 1


def test_first_apply_and_repeated_apply_do_not_restart_service(isolated_agent):
    home, env, run, calls = isolated_agent
    initial = run()
    assert initial.returncode == 0, initial.stderr
    marker = home / f".local/state/local-skills-mcp/{LABEL}.sha256"
    assert len(marker.read_text().strip()) == 64
    again = run()
    assert again.returncode == 0, again.stderr
    assert sum(call.startswith("bootstrap ") for call in calls()) == 1
    assert not any(call.startswith("bootout ") for call in calls())
    # Only the generated LaunchAgent stores the nonsecret Keychain account.
    assert "OPENAI_TUNNEL_API_KEY" not in (home / f"Library/LaunchAgents/{LABEL}.plist").read_text()


def test_demo_runtime_blocks_second_tunnel_client(isolated_agent):
    home, env, run, calls = isolated_agent
    Path(env["TEST_DEMO_RUNNING"]).touch()
    result = run()
    assert result.returncode != 0
    assert not any(call.startswith("bootstrap ") for call in calls())
    assert not (home / f".local/state/local-skills-mcp/{LABEL}.sha256").exists()


def test_unmanaged_active_launch_service_is_not_replaced(isolated_agent):
    _, env, run, calls = isolated_agent
    Path(env["TEST_SERVICE_RUNNING"]).touch()
    result = run()
    assert result.returncode != 0
    assert not any(call.startswith("bootout ") for call in calls())


def test_automatic_migration_from_previous_managed_launchagent(isolated_agent):
    home, env, run, calls = isolated_agent
    old_label = "com.example.skillport-mcp"
    old_plist = home / f"Library/LaunchAgents/{old_label}.plist"
    old_plist.write_text(
        f'<plist><string>{home}/.local/bin/skillport-mcp-launch</string></plist>'
    )
    old_marker = home / f"Library/Caches/chezmoi/{old_label}.sha256"
    old_marker.parent.mkdir(parents=True, exist_ok=True)
    old_marker.write_text("managed-previously")
    Path(env["TEST_LEGACY_SERVICE_RUNNING"]).touch()

    result = run()
    assert result.returncode == 0, result.stderr
    assert Path(env["TEST_SERVICE_RUNNING"]).exists()
    assert not Path(env["TEST_LEGACY_SERVICE_RUNNING"]).exists()
    assert not old_plist.exists()
    assert not old_marker.exists()
    assert any(call.startswith(f"bootout gui/") and old_label in call for call in calls())
    assert any(call.startswith("bootstrap ") and "local.skills.mcp" in call for call in calls())


def test_switching_to_professional_stops_only_managed_service(isolated_agent, profile_factory):
    home, env, run, calls = isolated_agent
    assert run().returncode == 0
    plist = home / f"Library/LaunchAgents/{LABEL}.plist"
    plist.unlink()  # The new profile no longer manages this file.
    professional = profile_factory.render("professional")
    hook = profile_factory.render_hook(
        professional.config, "professional", "run_after_25-ensure-local-skills-mcp.sh.tmpl", "transition"
    )
    result = subprocess.run(["/bin/sh", str(hook)], env=env,
                            text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert not Path(env["TEST_SERVICE_RUNNING"]).exists()
    assert not (home / f".local/state/local-skills-mcp/{LABEL}.sha256").exists()
    assert any(call.startswith("bootout gui/") and LABEL in call for call in calls())


def test_unconfigured_secret_backend_skips_optional_service(isolated_agent):
    home, env, run, calls = isolated_agent
    (home / ".config/local-skills-mcp/tunnel-id").unlink()

    result = run()

    assert result.returncode == 0, result.stderr
    assert not any(call.startswith("bootstrap ") for call in calls())
    assert not (home / ".local/state/local-skills-mcp").exists()


def test_configured_service_reports_credential_failure(isolated_agent):
    _, env, run, calls = isolated_agent
    Path(env["TEST_BWS_FAILURE"]).touch()

    result = run()

    assert result.returncode != 0
    assert not any(call.startswith("bootstrap ") for call in calls())


def test_backend_tunnel_change_restarts_managed_service(isolated_agent):
    home, env, run, calls = isolated_agent
    (home / ".config/local-skills-mcp/tunnel-id").unlink()
    env["TEST_BWS_ID"] = "tunnel_" + "a" * 32

    first = run()
    assert first.returncode == 0, first.stderr
    marker = home / f".local/state/local-skills-mcp/{LABEL}.sha256"
    first_hash = marker.read_text()

    env["TEST_BWS_ID"] = "tunnel_" + "b" * 32
    second = run()

    assert second.returncode == 0, second.stderr
    assert marker.read_text() != first_hash
    assert sum(call.startswith("bootstrap ") for call in calls()) == 2
    assert sum(call.startswith("bootout ") for call in calls()) == 1


def test_secret_based_tunnel_refuses_competing_client(isolated_agent):
    home, env, run, calls = isolated_agent
    (home / ".config/local-skills-mcp/tunnel-id").unlink()
    env["TEST_BWS_ID"] = "tunnel_" + "a" * 32
    Path(env["TEST_DEMO_RUNNING"]).touch()

    result = run()

    assert result.returncode != 0
    assert not any(call.startswith("bootstrap ") for call in calls())


def test_failed_reload_restores_prior_service_configuration(isolated_agent):
    home, env, run, calls = isolated_agent
    first = run()
    assert first.returncode == 0, first.stderr
    snapshot = home / ".local/state/local-skills-mcp/last-working.plist"
    assert snapshot.is_file()
    old_contents = snapshot.read_text()
    marker = home / f".local/state/local-skills-mcp/{LABEL}.sha256"
    old_hash = marker.read_text()

    plist = home / f"Library/LaunchAgents/{LABEL}.plist"
    plist.write_text(plist.read_text().replace("<integer>120</integer>", "<integer>180</integer>"))
    Path(env["TEST_FAIL_BOOTSTRAP"]).touch()

    second = run()

    assert second.returncode != 0
    assert Path(env["TEST_SERVICE_RUNNING"]).exists()
    assert marker.read_text() == old_hash
    assert snapshot.read_text() == old_contents
    assert any("bootstrap " in call and "last-working.plist" in call for call in calls())


def test_before_hook_captures_original_managed_plist(isolated_agent, profile_factory):
    home, env, run, _ = isolated_agent
    assert run().returncode == 0
    snapshot = home / ".local/state/local-skills-mcp/last-working.plist"
    snapshot.unlink()
    original = (home / f"Library/LaunchAgents/{LABEL}.plist").read_text()
    profile = profile_factory.render("personal")
    before = profile_factory.render_hook(
        profile.config, "personal", "run_before_24-snapshot-local-skills-mcp.sh.tmpl",
        "snapshot",
    )

    result = subprocess.run(
        ["/bin/sh", str(before)], env=env,
        text=True, capture_output=True, timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert snapshot.read_text() == original
    assert snapshot.stat().st_mode & 0o777 == 0o600
