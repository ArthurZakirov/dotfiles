"""Run Browser Use actions only through a verified regular Chrome connection."""

import fcntl
import http.client
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time

ROOT = Path.home() / ".local/share/dotfiles/browser-use"
RUNTIME = ROOT / "run"
PROFILE = Path.home() / "Library/Application Support/Google/Chrome"


def native(*args):
    return ["/usr/bin/osascript", "-l", "JavaScript", str(ROOT / "chrome-tabs.js"), *args]


def uses_login_home():
    return Path(pwd.getpwuid(os.getuid()).pw_dir).resolve() == Path.home().resolve()


def regular_pid():
    # Prefer the actual regular profile holder even if several Chrome instances run.
    try:
        holder = os.readlink(PROFILE / "SingletonLock").rsplit("-", 1)[-1]
    except (FileNotFoundError, PermissionError):
        holder = None
    if holder and holder.isdecimal():
        process = subprocess.run(["/bin/ps", "-p", holder, "-o", "uid=", "-o", "comm="],
                                 capture_output=True, text=True)
        identity = process.stdout.strip().split(None, 1)
        if (len(identity) == 2 and identity[0] == str(os.getuid()) and
                identity[1].endswith("/Google Chrome.app/Contents/MacOS/Google Chrome")):
            return int(holder)
    # If the entire Chrome directory is protected, exclude processes launched
    # with alternate user data. Never select a process merely by its port.
    if not uses_login_home():
        return None
    pids = json.loads(subprocess.check_output(native("--pids"), text=True))
    candidates = []
    for pid in pids:
        argv = subprocess.run(["/bin/ps", "-ww", "-o", "command=", "-p", str(pid)],
                              text=True, capture_output=True)
        if argv.returncode or not argv.stdout.strip():
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            raise RuntimeError("Cannot identify the running Chrome profile.")
        if "--user-data-dir" not in argv.stdout:
            candidates.append(pid)
    if len(candidates) > 1:
        raise RuntimeError("Multiple Chrome processes could be using the regular profile.")
    return candidates[0] if candidates else None


def ensure_regular_chrome():
    if regular_pid() is not None:
        return
    if not uses_login_home():
        raise RuntimeError("No Chrome holds the requested home directory's regular profile.")
    # A plain bundle activation can deliver the open event to an alternate
    # instance. A new normal launch lets Chrome select its default data directory.
    subprocess.run(["/usr/bin/open", "-n", "-g", "-b", "com.google.Chrome"], check=True)


def listener_ports(pid):
    result = subprocess.run(["/usr/sbin/lsof", "-nP", "-a", "-p", str(pid),
                             "-iTCP", "-sTCP:LISTEN", "-Fn"], capture_output=True, text=True)
    return [int(match[1]) for line in result.stdout.splitlines()
            if (match := re.fullmatch(r"n127\.0\.0\.1:(\d+)", line))]


def published_endpoint(pid):
    # A direct local GET follows no redirects and ignores environment proxies.
    choices = []
    for port in listener_ports(pid):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        try:
            conn.request("GET", "/json/version")
            response = conn.getresponse()
            prefix = f"ws://127.0.0.1:{port}/devtools/browser"
            if response.status == 404 and port == 9222:
                # Stable Chrome's approval-only server intentionally disables HTTP discovery.
                choices.append((port, prefix))
            elif response.status == 200:
                data = json.loads(response.read(16384))
                ws = data.get("webSocketDebuggerUrl", "") if isinstance(data, dict) else ""
                if isinstance(ws, str) and re.fullmatch(re.escape(prefix) + r"/[A-Za-z0-9-]+", ws):
                    choices.append((port, ws))
        except (OSError, http.client.HTTPException, ValueError):
            continue
        finally:
            conn.close()
    if len(choices) != 1:
        raise RuntimeError("Discovery file unreadable and no unique Chrome-owned debugging endpoint was found.")
    return choices[0]


def chrome_port(setup):
    from browser_use.browser.local import _left_over

    ensure_regular_chrome()
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
        if attempt == 24 and setup and len(json.loads(subprocess.check_output(native("--pids"), text=True))) == 1:
            print("Opening Chrome’s remote debugging page to inspect the current setting.", file=sys.stderr)
            subprocess.run(["/usr/bin/open", "-b", "com.google.Chrome",
                            "chrome://inspect/#remote-debugging"], check=True)
        time.sleep(0.2)
    raise RuntimeError("Regular Chrome has not published a current debugging endpoint.")


def daemon_generation(admin, pidfile):
    pid = admin._pending_pid_record(pidfile)
    started = admin._process_start_time(pid) if pid else None
    return (pid, started) if started else None


def prepare(setup):
    from browser_harness import admin
    from browser_harness import _ipc as ipc
    from browser_use.browser.local import require_debug_port

    pidfile = ipc.pid_path(admin.NAME)
    verified = RUNTIME / "verified-generation"
    generation = daemon_generation(admin, pidfile)
    if generation and verified.exists() and verified.read_text() == repr(generation):
        if admin.daemon_browser_kind() in {"local", "cdp"} and admin.daemon_browser_ready():
            return

    owner = None
    env = None
    try:
        port = chrome_port(setup)
        require_debug_port()
    except PermissionError as denied:
        owner = regular_pid()
        if not owner:
            raise
        try:
            port, ws = published_endpoint(owner)
        except RuntimeError as error:
            raise RuntimeError(f"{denied.strerror} reading {denied.filename}. {error}") from error
        env = {"BU_CDP_WS": ws}

    # Native local mode keeps the original handshake parked while a human reviews
    # Chrome's Allow sheet. A finite caller wait leaves that connection available.
    if env and admin._starting_daemon_pid() and not admin.daemon_alive():
        raise RuntimeError("An existing connection is starting. Review the pending Chrome prompt before retrying.")
    admin.ensure_daemon(wait=120, env=env)
    generation = daemon_generation(admin, pidfile)
    if not generation or admin.daemon_browser_kind() not in {"local", "cdp"}:
        raise RuntimeError("Could not verify the local browser connection.")
    # Discovery in the harness also knows about other Chromium browsers. Prove
    # the socket reaches regular Chrome before passing a task to that daemon.
    sockets = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-a", "-p", str(generation[0]), "-iTCP",
         "-sTCP:ESTABLISHED", "-Fn"], capture_output=True, text=True, check=False)
    if not any(line.endswith(f"->127.0.0.1:{port}") for line in sockets.stdout.splitlines()):
        raise RuntimeError("The connection to regular Chrome could not be verified.")
    if owner and (regular_pid() != owner or port not in listener_ports(owner)):
        raise RuntimeError("Chrome changed during connection verification.")
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
