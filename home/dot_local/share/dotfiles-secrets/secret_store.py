"""Reusable read-only secrets access for independent dotfiles integrations."""

from __future__ import annotations

import json
import os
import subprocess


def sanitized_environment(inherited: dict) -> dict:
    """Prevent credentials for the shared secrets backend reaching child services."""
    return {key: value for key, value in inherited.items() if key != "BWS_ACCESS_TOKEN"}


def read_secrets(names: set[str], account: str, inherited: dict | None = None) -> dict[str, str]:
    """Return only requested secret names. Never expose backend output in errors."""
    if not account:
        raise ValueError("No shared secrets account configured")
    try:
        keychain = subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", "BWS_ACCESS_TOKEN", "-w"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        token = keychain.stdout.rstrip("\n")
        if not token:
            raise ValueError("Empty shared secrets credential")
        env = dict(os.environ if inherited is None else inherited)
        env["BWS_ACCESS_TOKEN"] = token
        response = subprocess.run(
            ["bws", "secret", "list", "--output", "json"],
            env=env, capture_output=True, text=True, check=True, timeout=60,
        )
        records = json.loads(response.stdout)
        if not isinstance(records, list):
            raise ValueError("Invalid secrets response")
        result = {}
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Invalid secret record")
            key = record.get("key")
            if key not in names:
                continue
            value = record.get("value")
            if not isinstance(value, str) or not value or key in result:
                raise ValueError("Invalid or duplicate requested secret")
            result[key] = value
        return result
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        raise ValueError("Shared secrets unavailable or malformed") from None
