"""VS Code syntax highlighting for managed Lua templates."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_lua_templates_get_lua_highlighting():
    settings = json.loads((ROOT / ".vscode/settings.json").read_text())
    assert settings["files.associations"]["**/*.lua.tmpl"] == "lua"
