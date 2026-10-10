#!/usr/bin/env python3
"""Compatibility entry point for pytest-based profile checks."""

from pathlib import Path
import subprocess


def main() -> int:
    tests = Path(__file__).resolve().parents[1] / "tests" / "test_profiles.py"
    return subprocess.call(["pytest", "-q", str(tests)])


if __name__ == "__main__":
    raise SystemExit(main())
