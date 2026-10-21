"""Documentation contracts derived from authoritative repository sources.

External provider UI steps are intentionally linked, not snapshotted here.
"""

import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "docs/features"
MCP_DOC = FEATURES / "chatgpt-skills-mcp.md"
SECRETS_DOC = FEATURES / "secrets-management.md"
LAUNCHER = ROOT / "home/dot_local/share/local-skills-mcp/launch.py"
SECRETS_HELPER = ROOT / "home/dot_local/share/dotfiles-secrets/secret_store.py"


def _runtime_secret_names() -> set[str]:
    """Discover the runtime configuration keys without duplicating their names."""
    tree = ast.parse(LAUNCHER.read_text())
    runtime = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "runtime_environment"
    )
    return {
        node.value for node in ast.walk(runtime)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("OPENAI_TUNNEL_")
    }


def test_openai_secret_setup_stays_aligned_with_runtime():
    document = MCP_DOC.read_text()
    documented = set(re.findall(r"\*\*Name:\*\*\s*`([A-Z][A-Z0-9_]+)`", document))
    assert documented == _runtime_secret_names()
    tunnel_setup, key_setup = document.split("### 2. Create and save the runtime API key")
    assert "`OPENAI_TUNNEL_ID`" in tunnel_setup
    assert "`OPENAI_TUNNEL_API_KEY`" in key_setup


def test_bitwarden_keychain_instructions_match_provider():
    source = SECRETS_HELPER.read_text()
    doc = SECRETS_DOC.read_text()
    assert '"BWS_ACCESS_TOKEN"' in source
    assert "`BWS_ACCESS_TOKEN`" in doc


def test_documentation_links_resolve():
    # Both reader-facing routes and detailed implementation pages must stay navigable.
    for filename in (ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))):
        source = filename.read_text()
        for target in re.findall(r"\]\(([^)]+)\)", source):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path, sep, anchor = target.partition("#")
            destination = filename.parent / path
            assert destination.exists(), f"{filename}: broken link to {target}"
            if sep and destination.is_file():
                headings = re.findall(r"^#{1,6}\s+(.+)$", destination.read_text(), re.M)
                slugs = {
                    re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")
                    for heading in headings
                }
                assert anchor in slugs, f"{filename}: broken heading link to {target}"


def test_direct_bitwarden_cli_installer_is_declared_once_and_documented():
    manifest = ROOT / "dependencies/manual/personal.txt"
    installer = ROOT / "src/setup-actions.sh"
    orchestrator = ROOT / "src/shell-setup.sh"

    assert "bitwarden-secrets-manager" in manifest.read_text().splitlines()
    assert "install_bitwarden_secrets_manager()" in installer.read_text()
    assert "https://bws.bitwarden.com/install" in installer.read_text()
    assert "install_manual_dependencies" in orchestrator.read_text()

    provisioning = (ROOT / "docs/provisioning.md").read_text()
    inventory = (ROOT / "docs/tool-inventory.md").read_text()
    assert "dependencies/manual/personal.txt" in provisioning
    assert "src/setup-actions.sh" in provisioning
    assert "src/setup-actions.sh" in inventory
