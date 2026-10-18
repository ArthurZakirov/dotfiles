#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.15.1"]
# ///
"""Render Codex config.toml from stdin, changing only the versioned voice prompt."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import tomlkit

PROMPT_KEY = "experimental_realtime_ws_backend_prompt"


def render_prompt(content: str, prompt: str) -> str:
    if not prompt.strip():
        raise ValueError("the versioned Live Voice prompt is empty")

    document = tomlkit.parse(content)
    before = tomllib.loads(content)
    if tomlkit.dumps(document) != content:
        raise ValueError("tomlkit cannot preserve the original config formatting")

    if before.get(PROMPT_KEY) == prompt:
        return content

    previous_item = document.get(PROMPT_KEY)
    document[PROMPT_KEY] = tomlkit.string(prompt, multiline=True)
    updated = tomlkit.dumps(document)

    # Do not normalize comments, tables, or whitespace outside an existing key.
    # Inserting an absent key can legitimately add a blank line.
    if previous_item is not None:
        document[PROMPT_KEY] = previous_item
        if tomlkit.dumps(document) != content:
            raise ValueError("the prompt edit would alter unrelated config formatting")

    if tomllib.loads(updated) != {**before, PROMPT_KEY: prompt}:
        raise ValueError("updating the prompt would change other Codex settings")

    return updated


def codex_is_running() -> bool:
    """Codex is not a cooperating lock holder; avoid applying while it is active."""
    pgrep = shutil.which("pgrep")
    if pgrep is None:
        raise RuntimeError("Cannot check running Codex processes: pgrep unavailable")
    for name in ("ChatGPT", "codex"):
        process = subprocess.run(
            [pgrep, "-x", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if process.returncode == 0:
            return True
        if process.returncode != 1:
            raise RuntimeError(f"Cannot check running {name} processes")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", type=Path, required=True)
    args = parser.parse_args()

    # Chezmoi supplies the *current* machine-local config on stdin.
    original = sys.stdin.read()
    if os.environ.get("CHEZMOI_COMMAND") == "apply":
        destination = os.environ.get("CHEZMOI_DEST_DIR")
        if not destination:
            raise RuntimeError("Missing Chezmoi destination for safe apply")
        config = Path(destination) / ".codex/config.toml"
        if config.is_symlink():
            raise ValueError("refusing to replace a symlinked Codex config")

    updated = render_prompt(original, args.prompt.read_text(encoding="utf-8"))
    if updated != original and os.environ.get("CHEZMOI_COMMAND") == "apply" and codex_is_running():
        print(
            "Deferred Codex Live Voice prompt sync: quit ChatGPT Desktop and Codex CLI, "
            "then rerun chezmoi apply; chezmoi diff still shows the pending change.",
            file=sys.stderr,
        )
        updated = original

    # stdout is strictly the computed target file; no user-facing status text.
    sys.stdout.write(updated)


if __name__ == "__main__":
    main()
