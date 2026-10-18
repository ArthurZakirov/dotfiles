#!/usr/bin/env python3
"""Block Codex prompt submission inside a configured local-time window."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_REASON = (
    "Bedtime guard is active. Capture the thought offline and rest; "
    "Codex is available again after the configured end time."
)


def parse_clock(value: str) -> time:
    try:
        parsed = datetime.strptime(value, "%H:%M").time()
    except ValueError as error:
        raise ValueError(f"invalid time {value!r}; expected HH:MM") from error
    return parsed


def clock_now(timezone_name: str, override: str | None = None) -> datetime:
    timezone = None
    if timezone_name != "local":
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ValueError(
                f"timezone {timezone_name!r} is unavailable; use 'local' or install timezone data"
            ) from error

    if override:
        try:
            current = datetime.fromisoformat(override)
        except ValueError as error:
            raise ValueError("--now must be an ISO-8601 date and time") from error
        if timezone is not None:
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone)
            else:
                current = current.astimezone(timezone)
        return current

    if timezone is None:
        return datetime.now().astimezone()
    return datetime.now(timezone)


def in_window(current: time, start: time, end: time) -> bool:
    if start == end:
        raise ValueError("start and end must differ")
    if start < end:
        return start <= current < end
    return current >= start or current < end


def load_config(path: Path) -> dict[str, object]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"configuration not found: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read configuration: {path}") from error
    if not isinstance(config, dict):
        raise ValueError("configuration root must be an object")
    return config


def evaluate(config: dict[str, object], now_override: str | None = None) -> bool:
    enabled = config.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be true or false")
    if not enabled:
        return False

    start_value = config.get("start")
    end_value = config.get("end")
    timezone_name = config.get("timezone", "local")
    if not isinstance(start_value, str) or not isinstance(end_value, str):
        raise ValueError("start and end must be HH:MM strings")
    if not isinstance(timezone_name, str) or not timezone_name:
        raise ValueError("timezone must be 'local' or an IANA timezone name")

    start = parse_clock(start_value)
    end = parse_clock(end_value)
    current = clock_now(timezone_name, now_override).time().replace(tzinfo=None)
    return in_window(current, start, end)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--now", help=argparse.SUPPRESS)
    parser.add_argument("--managed-by", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    # Drain the hook payload so large prompts cannot leave the parent blocked on a full pipe.
    sys.stdin.buffer.read()
    try:
        config = load_config(args.config)
        blocked = evaluate(config, args.now)
    except ValueError as error:
        print(f"bedtime-device-guard: {error}", file=sys.stderr)
        return 1

    if blocked:
        reason = config.get("reason", DEFAULT_REASON)
        if not isinstance(reason, str) or not reason.strip():
            reason = DEFAULT_REASON
        print(json.dumps({"decision": "block", "reason": reason}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
