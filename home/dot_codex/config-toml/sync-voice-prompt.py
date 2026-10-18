#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.15.1"]
# ///
"""Synchronize only the versioned Live Voice prompt into Codex's local TOML."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import tempfile
import tomllib

import tomlkit

PROMPT_KEY = "experimental_realtime_ws_backend_prompt"


def sync_prompt(config_path: Path, prompt_path: Path) -> bool:
    prompt = prompt_path.read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("the versioned Live Voice prompt is empty")

    if config_path.is_symlink():
        raise ValueError("refusing to replace a symlinked Codex config")
    original = config_path.read_bytes() if config_path.exists() else None
    content = original.decode("utf-8") if original is not None else ""
    document = tomlkit.parse(content)
    before = tomllib.loads(content)

    # Do not rewrite files that tomlkit cannot round-trip byte-for-byte.
    if tomlkit.dumps(document) != content:
        raise ValueError("tomlkit cannot preserve the original config formatting")

    if before.get(PROMPT_KEY) == prompt:
        return False

    previous_item = document.get(PROMPT_KEY)
    document[PROMPT_KEY] = tomlkit.string(prompt, multiline=True)
    updated = tomlkit.dumps(document)

    # Replacing an existing key must leave every other byte untouched.
    # Inserting a previously absent key can legitimately add a blank line.
    if previous_item is not None:
        document[PROMPT_KEY] = previous_item
        if tomlkit.dumps(document) != content:
            raise ValueError("the prompt edit would alter unrelated config formatting")
    expected = {**before, PROMPT_KEY: prompt}
    if tomllib.loads(updated) != expected:
        raise ValueError("updating the prompt would change other Codex settings")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(config_path.stat().st_mode) if original is not None else 0o600
    fd, temporary_name = tempfile.mkstemp(prefix=".config.toml-", dir=config_path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as temporary:
            temporary.write(updated.encode("utf-8"))
            temporary.flush()
            os.fsync(temporary.fileno())

        # Refuse an observed concurrent modification instead of overwriting it.
        if original is None:
            if config_path.exists():
                raise RuntimeError("Codex created config.toml during synchronization")
        elif not config_path.exists() or config_path.read_bytes() != original:
            raise RuntimeError("Codex changed config.toml during synchronization")

        os.replace(temporary_name, config_path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    parser.add_argument("--config", type=Path, default=codex_home / "config.toml")
    parser.add_argument(
        "--prompt",
        type=Path,
        default=codex_home / "config-toml/realtime-voice-backend-prompt.md",
    )
    args = parser.parse_args()
    changed = sync_prompt(args.config, args.prompt)
    print("Updated Codex Live Voice prompt." if changed else "Codex Live Voice prompt already current.")


if __name__ == "__main__":
    main()
