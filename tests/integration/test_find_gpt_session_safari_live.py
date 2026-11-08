"""Opt-in live regression: Safari background AX search and focus recovery.

Run on a logged-in Mac, not in CI:
  FIND_GPT_SAFARI_E2E=1 FIND_GPT_SAFARI_TEST_QUERY="pull/65" \
    pytest -q tests/integration/test_find_gpt_session_safari_live.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("FIND_GPT_SAFARI_E2E") != "1",
    reason="Requires logged-in Safari and explicitly opted-in foreground GUI test",
)


def _foreground_bundle() -> str:
    # Match the NSWorkspace API used by the native Safari adapter.
    # System Events' frontmost AX process can lag behind a completed
    # NSRunningApplication activation, causing false foreground failures.
    result = subprocess.run(
        [
            "/usr/bin/swift", "-e",
            'import AppKit;print(NSWorkspace.shared.frontmostApplication?'
            '.bundleIdentifier ?? "none")',
        ],
        check=True, capture_output=True, text=True, timeout=15,
    )
    return result.stdout.strip()


def test_live_safari_background_query_resolves_chat_and_restores_focus():
    term = os.environ.get("FIND_GPT_SAFARI_TEST_QUERY", "pull/65")
    home = Path.home()
    executable = home / ".local/bin/find-gpt-session"
    assert executable.is_file(), "Install the managed find-gpt-session CLI"

    original = _foreground_bundle()
    assert original != "com.apple.Safari", (
        "Run from Warp or another foreground app to test focus recovery"
    )

    result = subprocess.run(
        [str(executable), "--provider", "safari", "--limit", "2",
         "--json", "search", term],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["results"], payload.get("warnings")
    assert all(
        hit["url"].startswith("https://chatgpt.com/c/")
        for hit in payload["results"]
    )
    assert _foreground_bundle() == original
