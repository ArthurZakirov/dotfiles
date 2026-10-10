#!/usr/bin/env python3
"""Entry point for non-destructive chezmoi profile behavior tests."""

from pathlib import Path
import sys

# Allow running this file directly from anywhere, including CI.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_profiles import main


if __name__ == "__main__":
    main()
