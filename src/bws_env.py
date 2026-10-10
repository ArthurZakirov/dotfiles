#!/usr/bin/env python3
"""Convert BWS JSON secrets to NUL-delimited environment key/value pairs.

Never interpret either the key or the value as shell code. Intended for
consumption by zsh's read -d '' and typeset -gx.
"""

import json
import re
import sys

ENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def main() -> None:
    secrets = json.load(sys.stdin)
    if not isinstance(secrets, list):
        raise ValueError("Expected an array of Bitwarden secrets")
    for secret in secrets:
        key = secret["key"]
        value = secret["value"]
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Secret keys and values must be strings")
        if not ENV_KEY.fullmatch(key):
            continue  # Same behavior as BWS env output for invalid names.
        sys.stdout.buffer.write(key.encode() + b"\0" + value.encode() + b"\0")


if __name__ == "__main__":
    main()
