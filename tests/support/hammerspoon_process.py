"""Fake process adapters for isolated Hammerspoon command integration tests."""

from pathlib import Path


def executable(directory: Path, name: str, content: str) -> Path:
    file = directory / name
    file.write_text("#!/bin/sh\n" + content)
    file.chmod(0o755)
    return file
