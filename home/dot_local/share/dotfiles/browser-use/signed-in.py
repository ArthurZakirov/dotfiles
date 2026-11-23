"""Run Browser Use actions only through a verified regular Chrome connection."""

import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path.home() / ".local/share/dotfiles/browser-use"
RUNTIME = ROOT / "run"
PROFILE = Path.home() / "Library/Application Support/Google/Chrome"


def chrome_port(setup):
    from browser_harness.daemon import browser_running_for_profile
    from browser_use.browser.local import _left_over

    if not browser_running_for_profile(PROFILE):
        subprocess.run(["/usr/bin/open", "-g", "-b", "com.google.Chrome"], check=True)
    marker = PROFILE / "DevToolsActivePort"
    for attempt in range(325 if setup else 25):
        try:
            lines = marker.read_text().splitlines()
        except FileNotFoundError:
            lines = []
        if lines and lines[0].isascii() and lines[0].isdecimal():
            port = int(lines[0]) if len(lines[0]) <= 5 else 0
            if 0 < port <= 65535 and not _left_over(PROFILE):
                # An old marker can survive a restart. Only trust a listener held
                # by the Chrome process that owns this regular profile.
                holder = os.readlink(PROFILE / "SingletonLock").rsplit("-", 1)[-1]
                if holder.isdecimal():
                    listen = subprocess.run(
                        ["/usr/sbin/lsof", "-nP", "-a", "-p", holder,
                         f"-iTCP@127.0.0.1:{port}", "-sTCP:LISTEN", "-Fp"],
                        capture_output=True, text=True)
                    if f"p{holder}" in listen.stdout.splitlines():
                        return port
        if attempt == 24 and setup:
            print("In Chrome, enable ‘Allow remote debugging for this browser instance’.", file=sys.stderr)
            subprocess.run(["/usr/bin/open", "-b", "com.google.Chrome",
                            "chrome://inspect/#remote-debugging"], check=True)
        time.sleep(0.2)
    raise RuntimeError("Regular Chrome has not published a current debugging endpoint.")


def prepare(setup):
    from browser_harness import admin
    from browser_harness import _ipc as ipc
    from browser_use.browser.local import require_debug_port

    pidfile = ipc.pid_path(admin.NAME)
    verified = RUNTIME / "verified-generation"
    generation = admin._fingerprinted_pending_generation(pidfile)
    if generation and verified.exists() and verified.read_text() == repr(generation):
        if admin.daemon_browser_kind() == "local" and admin.daemon_browser_ready():
            return

    port = chrome_port(setup)
    require_debug_port()
    # Native local mode keeps the original handshake parked while a human reviews
    # Chrome's Allow sheet. A finite caller wait leaves that connection available.
    admin.ensure_daemon(wait=120)
    generation = admin._fingerprinted_pending_generation(pidfile)
    if not generation or admin.daemon_browser_kind() != "local":
        raise RuntimeError("Could not verify the local browser connection.")
    # Discovery in the harness also knows about other Chromium browsers. Prove
    # the socket reaches regular Chrome before passing a task to that daemon.
    sockets = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-a", "-p", str(generation[0]), "-iTCP",
         "-sTCP:ESTABLISHED", "-Fn"], capture_output=True, text=True, check=False)
    if not any(line.endswith(f"->127.0.0.1:{port}") for line in sockets.stdout.splitlines()):
        raise RuntimeError("The connection to regular Chrome could not be verified.")
    admin.require_existing_daemon()
    verified.write_text(repr(generation))


def main():
    if sys.argv[1:] not in ([], ["--check"], ["--setup"]):
        raise SystemExit("Usage: browser-use-signed-in [--check | --setup]; pass browser actions via stdin.")
    if len(sys.argv) == 1 and sys.stdin.isatty():
        raise SystemExit("Pass Browser Use Python via stdin, or use --check.")
    os.environ.update(BH_RUNTIME_DIR=str(RUNTIME), BH_RUNTIME_DIR_SHARED="1",
                      BH_TMP_DIR=str(RUNTIME), BH_TMP_DIR_SHARED="1", BU_NAME="signed-in",
                      BH_REQUIRE_EXISTING_DAEMON="1", BU_CDP_URL="", BU_CDP_WS="",
                      BU_AUTOSPAWN="", BU_BROWSER_ID="", BH_TAB_MARKER="0", BH_TELEMETRY="0")
    RUNTIME.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (RUNTIME / "prepare.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prepare(sys.argv[1:] == ["--setup"])
        if sys.argv[1:]:
            print("Connected to regular Chrome.")
            return
        # Hold the lock through this action so another managed caller cannot
        # switch the selected tab between its identity check and its click.
        os.set_inheritable(lock.fileno(), True)
        cli = str(ROOT / "bin/browser-use")
        os.execv(cli, [cli])


if __name__ == "__main__":
    try:
        main()
    except PermissionError as error:
        sys.exit(f"Access denied by this execution context: {error.filename or error}.")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(f"Signed-in Chrome unavailable: {error}")
