"""Start the local skills tunnel using the shared dotfiles credential provider."""

import importlib.util
import os
import re
import shutil
import sys
from pathlib import Path

TUNNEL_PATTERN = re.compile(r"^tunnel_[0-9a-f]{32}$")


def credential_provider(home: Path):
    """Load the reusable dotfiles secret provider without bundling a copy."""
    source = home / ".local/share/dotfiles-secrets/secret_store.py"
    spec = importlib.util.spec_from_file_location("dotfiles_secret_store", source)
    if spec is None or spec.loader is None:
        raise ValueError("Shared secrets support is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def select_tunnel_id(home: Path, secrets: dict[str, str]) -> str:
    """Use the locally configured tunnel, preserving existing installations."""
    config = home / ".config/local-skills-mcp/tunnel-id"
    legacy = home / ".config/skillport-mcp/tunnel-id"
    for path in (config, legacy):
        if path.is_file():
            candidate = path.read_text(encoding="utf-8").strip()
            break
    else:
        candidate = secrets.get("OPENAI_TUNNEL_ID", "")
    if not TUNNEL_PATTERN.fullmatch(candidate):
        raise ValueError("No valid local skills tunnel is configured")
    return candidate


def runtime_environment(home: Path, account: str, inherited: dict) -> tuple[dict, str]:
    provider = credential_provider(home)
    secrets = provider.read_secrets(
        {"OPENAI_TUNNEL_API_KEY", "OPENAI_TUNNEL_ID"}, account, inherited
    )
    if "OPENAI_TUNNEL_API_KEY" not in secrets:
        raise ValueError("Tunnel runtime credential is unavailable")
    tunnel_id = select_tunnel_id(home, secrets)
    runtime = provider.sanitized_environment(inherited)
    for key in ("OPENAI_TUNNEL_API_KEY", "OPENAI_TUNNEL_ID"):
        runtime.pop(key, None)
    runtime["CONTROL_PLANE_API_KEY"] = secrets["OPENAI_TUNNEL_API_KEY"]
    return runtime, tunnel_id


def main() -> int:
    try:
        home = Path.home()
        account = os.environ.get("DOTFILES_SECRETS_ACCOUNT", "")
        runtime, tunnel_id = runtime_environment(home, account, os.environ)
        if sys.argv[1:] == ["--configured"]:
            return 0
        if len(sys.argv) != 1:
            return 2
        python = home / ".local/share/local-skills-mcp/.venv/bin/python"
        server = home / ".local/share/local-skills-mcp/server.py"
        secret_store = home / ".local/share/dotfiles-secrets/secret_store.py"
        if not all(path.is_file() for path in (python, server, secret_store)):
            raise ValueError("Local skills environment is not installed")
        cli = shutil.which("tunnel-client")
        if cli is None:
            raise ValueError("Tunnel client unavailable")
        os.execvpe(cli, [
            cli, "run", "--control-plane.tunnel-id", tunnel_id,
            "--mcp.command", str(home / ".local/bin/local-skills-mcp-server"),
            "--health.listen-addr", "127.0.0.1:0",
        ], runtime)
    except (ValueError, OSError, TypeError):
        print("Local skills tunnel could not start: check shared credentials and tunnel configuration.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
