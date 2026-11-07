#!/usr/bin/env python3
"""Conservative cleanup of orphaned Google Chrome APFS code-sign clones."""
import argparse
import datetime
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

CHROME_EXECUTABLE = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CLONE_PATTERN = re.compile(r"code_sign_clone\.[A-Za-z0-9]{6}\Z")
MIN_AGE_SECONDS = 48 * 3600
START_MARGIN_SECONDS = 30 * 60


def chrome_start_times():
    """Find the start time of every *currently running* branded Chrome main process."""
    listing = subprocess.check_output(
        ["/bin/ps", "-axo", "pid=,comm="], text=True
    )
    starts = []
    for line in listing.splitlines():
        match = re.match(r"\s*(\d+)\s+(.+)$", line)
        if not match or match.group(2) != CHROME_EXECUTABLE:
            continue
        started = subprocess.check_output(
            ["/bin/ps", "-p", match.group(1), "-o", "lstart="], text=True
        ).strip()
        if not started:
            raise RuntimeError("Chrome process disappeared while inspecting it")
        normalized = " ".join(started.split())
        dt = datetime.datetime.strptime(normalized, "%a %b %d %H:%M:%S %Y")
        starts.append(time.mktime(dt.timetuple()))
    return starts


def eligible(birth_time, starts, now, newest_birth):
    """Never remove new clones, Chrome's active clone, or the newest while Chrome runs."""
    if now - birth_time < MIN_AGE_SECONDS:
        return False
    if any(abs(birth_time - started) <= START_MARGIN_SECONDS for started in starts):
        return False
    if starts and birth_time == newest_birth:
        return False
    return True


def cleanup(dry_run=False, root=None, starts=None, now=None):
    if root is None:
        tmp_dir = Path(
            subprocess.check_output(
                ["/usr/bin/getconf", "DARWIN_USER_TEMP_DIR"], text=True
            ).strip()
        ).resolve()
        if tmp_dir.name != "T":
            raise RuntimeError("Unexpected macOS per-user temporary directory")
        root = tmp_dir.parent / "X" / "com.google.Chrome.code_sign_clone"
    root = Path(root)
    if not root.exists():
        return {"removed": [], "retained": [], "reason": "no clone directory"}
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("Unsafe clone directory")
    # Fail closed if process inspection fails: never delete based on a guess.
    starts = chrome_start_times() if starts is None else starts
    now = time.time() if now is None else now
    entries = [
        p for p in root.iterdir()
        if CLONE_PATTERN.fullmatch(p.name) and p.is_dir() and not p.is_symlink()
    ]
    births = {p: getattr(p.stat(), "st_birthtime", p.stat().st_ctime) for p in entries}
    newest_birth = max(births.values(), default=0)
    removed, retained = [], []
    for p, birth in births.items():
        if not eligible(birth, starts, now, newest_birth):
            retained.append(p.name)
            continue
        if not dry_run:
            shutil.rmtree(p)
        removed.append(p.name)
    return {"removed": removed, "retained": retained, "dry_run": dry_run}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(cleanup(dry_run=args.dry_run), sort_keys=True))
    except Exception as exc:
        print(json.dumps({"error": str(exc), "action": "no further deletion"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
