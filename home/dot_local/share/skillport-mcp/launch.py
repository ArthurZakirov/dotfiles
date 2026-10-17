"""Start one local tunnel without exposing the runtime secret in files or argv."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TUNNEL_PATTERN = re.compile(r"^tunnel_[A-Za-z0-9_-]{8,128}$")


def runtime_environment(home: Path, account: str, inherited: dict) -> tuple[dict, str]:
    tunnel_file = home / ".config/skillport-mcp/tunnel-id"
    tunnel_id = tunnel_file.read_text(encoding="utf-8").strip()
    if not TUNNEL_PATTERN.fullmatch(tunnel_id):
        raise ValueError("Invalid tunnel ID; run skillport-mcp-configure")
    if not account:
        raise ValueError("Missing Bitwarden Keychain account")

    security = subprocess.run(
        ["security", "find-generic-password", "-a", account,
         "-s", "BWS_ACCESS_TOKEN", "-w"],
        capture_output=True, check=True, text=True,
    )
    secret_env = inherited.copy()
    secret_env["BWS_ACCESS_TOKEN"] = security.stdout.rstrip("\n")
    result = subprocess.run(
        ["bws", "secret", "list", "--output", "json"],
        env=secret_env, capture_output=True, check=True, text=True,
    )
    data = json.loads(result.stdout)
    items = data if isinstance(data, list) else data.get("data", [])
    matches = [item["value"] for item in items
               if isinstance(item, dict) and item.get("key") == "OPENAI_TUNNEL_API_KEY"]
    if len(matches) != 1 or not matches[0]:
        raise ValueError("Expected one OPENAI_TUNNEL_API_KEY in Bitwarden Secrets Manager")
    # The BWS access token stays in the short-lived subprocess and is never
    # inherited by the tunnel or its MCP child.
    runtime = inherited.copy()
    runtime.pop("BWS_ACCESS_TOKEN", None)
    runtime.pop("OPENAI_TUNNEL_API_KEY", None)
    runtime["CONTROL_PLANE_API_KEY"] = matches[0]
    return runtime, tunnel_id


def main() -> int:
    try:
        home = Path.home()
        account = os.environ.get("BWS_KEYCHAIN_ACCOUNT", "")
        runtime, tunnel_id = runtime_environment(home, account, os.environ)
        python = home / ".local/share/skillport-mcp/.venv/bin/python"
        server = home / ".local/share/skillport-mcp/server.py"
        if not python.is_file() or not server.is_file():
            raise ValueError("FastMCP environment missing; apply dotfiles setup first")
        cli = shutil.which("tunnel-client")
        if cli is None:
            raise ValueError("tunnel-client is not installed")
        command = [
            cli, "run", "--control-plane.tunnel-id", tunnel_id,
            "--mcp.command", str(home / ".local/bin/skillport-mcp-server"),
            "--health.listen-addr", "127.0.0.1:0",
        ]
        os.execvpe(cli, command, runtime)
    except (ValueError, OSError, subprocess.SubprocessError, json.JSONDecodeError):
        # Never include subprocess stderr/stdout or secret material in logs.
        print("SkillPort MCP could not start: check tunnel ID, Keychain, Bitwarden and dependencies.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
