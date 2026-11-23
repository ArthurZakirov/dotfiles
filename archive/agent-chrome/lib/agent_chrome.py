"""macOS signed-in Chrome connection lifecycle for agent-chrome."""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CLI = ["agent-browser", "--session", "dotfiles-chrome"]
AUTO = [*CLI, "--auto-connect", "--pin-tab"]
DIRECT = [*CLI, "--pin-tab"]
DISCOVERY_ERRORS = {
    "No running Chrome instance found. Launch Chrome with --remote-debugging-port or use --cdp.",
    "No running debuggable Chrome found",
}


def report(message):
    print("agent-chrome: " + message, file=sys.stderr)


def output(result):
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


def diagnostic(result):
    try:
        response = json.loads(result.stdout)
        if isinstance(response, dict) and response.get("success") is False:
            return str(response.get("error", ""))
    except (ValueError, UnicodeError):
        pass
    return result.stderr.decode(errors="replace").strip()


def discovery_failed(result):
    message = re.sub(r"\x1b\[[0-9;]*m", "", diagnostic(result))
    # Newer versions can print a project-config warning before the diagnostic.
    lines = message.splitlines()
    return result.returncode == 1 and bool(lines) and re.sub(
        r"^(?:✗ |Error: )?(?:Auto-launch failed: )?", "", lines[-1]
    ) in DISCOVERY_ERRORS


def approval_uncertain(result):
    if result.returncode == 0:
        return False
    # A wait for a DOM element can time out on a perfectly healthy connection.
    # Only connection/setup diagnostics are relevant to Chrome approval here.
    message = diagnostic(result).lower()
    if "approval pending" in message:
        return True
    return ("timeout" in message or "timed out" in message) and any(
        hint in message for hint in ("connect", "attach", "websocket", "devtools", "browser launch")
    )


def chrome_process():
    result = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True)
    if result.stderr or result.returncode not in (0, 1):
        return "unknown"
    return "running" if result.returncode == 0 else "closed"


def listeners():
    result = subprocess.run(["lsof", "-nP", "-a", "-c", "/^Google Chrome$/",
                             "-iTCP", "-sTCP:LISTEN", "-Fn"], capture_output=True)
    if result.returncode:
        return None
    endpoints = set()
    pid = None
    for line in result.stdout.decode(errors="replace").splitlines():
        if line.startswith("p"):
            pid = line[1:] if line[1:].isdigit() else None
        match = re.fullmatch(r"n(?:127\.0\.0\.1|\[::1\]):([0-9]+)", line)
        if pid and match and 0 < int(match[1]) <= 65535:
            endpoints.add((pid, str(int(match[1]))))
    return endpoints


def unique_listener():
    endpoints = listeners()
    return list(endpoints.pop()) if endpoints and len(endpoints) == 1 else None


def run_locked(state_file, command, args, stdin):
    def save(value):
        # Rename under a separate, stable lock inode. A killed process cannot
        # leave a partial state file that a second chat mistakes for a reset.
        with tempfile.NamedTemporaryFile(dir=state_file.parent, delete=False) as temp:
            temp.write(json.dumps(value).encode())
        os.replace(temp.name, state_file)

    def invoke(prefix, arguments, data=None):
        return subprocess.run([*prefix, *arguments], input=data, capture_output=True)

    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    process = chrome_process()
    if process == "closed" and state:
        save({})
        state = {}
    if state.get("pending"):
        if args != ["tab", "list"] or os.environ.get("AGENT_CHROME_RETRY_AFTER_APPROVAL") != "1":
            report("previous connection is awaiting confirmation. No new connection attempted.")
            return 1
    if command == "connect":
        result = invoke(DIRECT, args)
        if result.returncode == 0:
            verified = unique_listener()
            save({"endpoint": verified} if verified and args[-1] == verified[1] else {})
        else:
            save({"pending": True})
        return output(result)
    if process == "unknown":
        report("Chrome process inspection unavailable; browser state unknown. Attempting normal connection.")

    endpoint = state.get("endpoint")
    if endpoint:
        current = listeners()
        if not current or (tuple(endpoint) not in current and len(current) != 1):
            report("previous Chrome listener could not be verified. No new connection attempted.")
            return 1
        if tuple(endpoint) not in current:
            endpoint = None
            save({})
    if endpoint:
        # Use the same launch identity as connect <port>. Switching back to
        # auto-connect would cause agent-browser to replace the live connection.
        prefix = [*CLI, "--cdp", endpoint[1], "--pin-tab"]
    else:
        prefix = AUTO
    if command == "chat":
        # exec preserves the caller's terminal and releases the non-inheritable
        # lock descriptor, so a long interactive chat cannot starve other tasks.
        os.execvp(prefix[0], [*prefix, *args])
    result = invoke(prefix, args, stdin)
    if approval_uncertain(result):
        save({"pending": True, "endpoint": endpoint})
        report("command timed out or approval may be pending. No new connection attempted.")
        return output(result)
    if endpoint or not discovery_failed(result):
        if result.returncode == 0 and state.get("pending"):
            save({"endpoint": endpoint})
        return output(result)

    process = chrome_process()
    if process == "unknown":
        report("Chrome process inspection unavailable; browser state unknown.")
        return output(result)
    if process == "closed":
        if subprocess.run(["open", "-a", "Google Chrome"]).returncode:
            report("ordinary Chrome launch failed; retry not attempted.")
            return 1
        for attempt in range(11):
            process = chrome_process()
            if process != "closed":
                break
            if attempt == 10:
                report("Chrome did not become observable after launch; retry not attempted.")
                return 1
            subprocess.run(["sleep", "1"], check=True)
        if process == "unknown":
            report("Chrome process inspection unavailable after launch; browser state unknown.")
        # Run the same running-Chrome recovery below if startup discovery fails.
        result = invoke(AUTO, args, stdin)
        if not discovery_failed(result):
            if approval_uncertain(result):
                save({"pending": True})
            return output(result)

    endpoint = unique_listener()
    if endpoint is None:
        report("no unique Chrome loopback port verified; automatic recovery stopped.")
        return output(result)
    save({"pending": True, "endpoint": endpoint})
    connected = invoke(DIRECT, ["connect", endpoint[1]])
    if connected.returncode:
        report("explicit connection failed. No further attachment until confirmation.")
        return output(connected)
    tabs = invoke(DIRECT, ["tab", "list"])
    if tabs.returncode:
        report("explicit connection could not list tabs. No further attachment until confirmation.")
        return output(tabs)
    save({"endpoint": endpoint})
    report("recovered the existing Chrome connection and verified tab access.")
    if args == ["tab", "list"]:
        return output(tabs)
    if command in ("snapshot", "get") or args == ["--json", "tab", "list"]:
        return output(invoke(DIRECT, args, stdin))
    report("original command was not repeated. Inspect the task tab with a fresh snapshot before continuing.")
    return output(result)


def main():
    command, stdin_mode, *args = sys.argv[1:]
    stdin = sys.stdin.buffer.read() if stdin_mode == "yes" else None
    directory = Path.home() / "Library/Caches/agent-chrome"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / "connection.lock").open("a") as lock:
        # Competing chats must not start simultaneous permission dialogs.
        fcntl.flock(lock, fcntl.LOCK_EX)
        return run_locked(directory / "connection.json", command, args, stdin)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        report(str(error))
        sys.exit(1)
