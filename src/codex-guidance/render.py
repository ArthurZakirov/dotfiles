#!/usr/bin/env python3
"""Regenerate the versioned Codex guidance artifacts in the chezmoi source tree.

The canonical components, manifest and generator belong to this checkout only.
No source bundle or generator is installed in the user's ~/.codex directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "home" / "dot_codex"
GUIDANCE = Path(__file__).resolve().parent


def build() -> dict[Path, bytes]:
    with tempfile.TemporaryDirectory(prefix="dotfiles-codex-guidance-") as scratch:
        workspace = Path(scratch)
        codex_home = workspace / ".codex"
        subprocess.run(
            [
                sys.executable,
                str(GUIDANCE / "scripts" / "bootstrap-agents-md.py"),
                "--manifest", str(GUIDANCE / "global-guidance" / "agents-md-manifest.yaml"),
                "--codex-home", str(codex_home),
                "--claude-home", str(workspace / ".claude"),
                "--opencode-home", str(workspace / ".config" / "opencode"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        refs = codex_home / "agents-md-references"
        return {
            Path("AGENTS.md.tmpl"): (codex_home / "AGENTS.md").read_bytes(),
            **{
                Path("agents-md-references") / source.name: source.read_bytes()
                for source in refs.iterdir()
                if source.is_file()
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check versioned outputs without changing files")
    args = parser.parse_args()
    expected = build()
    target_paths = {
        Path("AGENTS.md.tmpl"),
        *(
            Path("agents-md-references") / path.name
            for path in (TARGET / "agents-md-references").glob("*")
            if path.is_file()
        ),
    }
    differences = [
        path for path in sorted(expected.keys() | target_paths)
        if path not in expected
        or not (TARGET / path).is_file()
        or (TARGET / path).read_bytes() != expected[path]
    ]
    if args.check:
        if differences:
            print("Outdated Codex guidance:", ", ".join(map(str, differences)), file=sys.stderr)
            return 1
        print("Codex guidance matches canonical sources.")
        return 0
    for path, content in expected.items():
        destination = TARGET / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    for path in target_paths - expected.keys():
        (TARGET / path).unlink()
    print(f"Updated {len(expected)} Codex guidance artifacts in {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
