"""Infrastructure adapters for opening verified Codex and ChatGPT sessions."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import uuid
from urllib.parse import urlsplit

from .core import SessionHit
from codex_history.sqlite import open_snapshot


class LaunchError(RuntimeError):
    """Opening a session failed without claiming a completed action."""


@dataclass
class OpenResult:
    requested: int
    dispatched: list[dict[str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def asdict(self) -> dict:
        return {
            "requested": self.requested,
            "dispatched": self.dispatched,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def verified_chat_url(address: str | None) -> str | None:
    if not address:
        return None
    try:
        parsed = urlsplit(address)
    except ValueError:
        return None
    if parsed.scheme != "https" or parsed.hostname != "chatgpt.com" or parsed.username:
        return None
    if parsed.password or parsed.port not in (None, 443):
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "c":
        identifier = parts[1]
    elif len(parts) == 4 and parts[0] == "g" and parts[2] == "c":
        identifier = parts[3]
    else:
        return None
    try:
        uuid.UUID(identifier)
    except ValueError:
        return None
    return "https://chatgpt.com" + parsed.path


def _validated_session_id(value: str | None) -> str:
    if not value:
        raise LaunchError("Codex session has no verified session ID")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise LaunchError("Invalid Codex session ID") from exc


def _codex_working_dir(session_id: str, home: Path) -> Path:
    db = home / ".codex/state_5.sqlite"
    if db.is_file():
        try:
            with closing(open_snapshot(db)) as con:
                con.execute("PRAGMA query_only=ON")
                row = con.execute("SELECT cwd FROM threads WHERE id=?", (session_id,)).fetchone()
            if row and isinstance(row[0], str) and Path(row[0]).is_dir():
                return Path(row[0]).resolve()
        except (sqlite3.Error, OSError, RuntimeError):
            pass
    return home


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


class WarpTabLauncher:
    """Launch each Codex resume command via a Warp Tab Config in the active window."""

    PREFIX = "find_gpt_session_"

    def __init__(self, home: Path | None = None, *, runner=subprocess.run):
        self.home = home or Path.home()
        self.folder = self.home / ".warp/tab_configs"
        self.runner = runner

    def _prune_old_configs(self) -> None:
        threshold = time.time() - 3600
        for item in self.folder.glob(self.PREFIX + "*.toml"):
            try:
                if item.is_file() and item.stat().st_mtime < threshold:
                    item.unlink()
            except OSError:
                continue

    def open_session(self, session_id: str) -> None:
        session_id = _validated_session_id(session_id)
        self.folder.mkdir(parents=True, exist_ok=True)
        self._prune_old_configs()
        directory = _codex_working_dir(session_id, self.home)
        # Unique config per launch prevents a race when several tabs open.
        name = self.PREFIX + uuid.uuid4().hex
        target = self.folder / (name + ".toml")
        contents = (
            f"name = {_toml_string('Codex ' + session_id[:8])}\n"
            f"title = {_toml_string('Codex ' + session_id[:8])}\n"
            "[[panes]]\n"
            'id = "main"\n'
            'type = "terminal"\n'
            f"directory = {_toml_string(str(directory))}\n"
            f"commands = [{_toml_string('codex resume ' + session_id)}]\n"
        )
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(contents)
        try:
            result = self.runner(
                ["/usr/bin/open", f"warp://tab_config/{name}"],
                text=True, capture_output=True, check=False, timeout=15,
            )
            if result.returncode:
                raise LaunchError("Warp could not open the Codex tab")
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LaunchError("Warp tab opening failed") from exc

    def reveal(self) -> None:
        """Activate after every destination has opened so Chrome cannot hide Warp."""
        try:
            result = self.runner(
                ["/usr/bin/osascript", "-e",
                 'tell application id "dev.warp.Warp-Stable" to activate'],
                text=True, capture_output=True, check=False, timeout=10,
            )
            if result.returncode:
                raise LaunchError("Warp opened tabs but could not be brought forward")
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LaunchError("Warp opened tabs but activation failed") from exc


class ChromeTabLauncher:
    """Open all verified ChatGPT links in tabs of one existing Chrome window."""

    APPLESCRIPT = '''
on run argv
    tell application "Google Chrome"
        if (count of windows) is 0 then make new window
        set destinationWindow to front window
        repeat with linkText in argv
            tell destinationWindow
                make new tab at end of tabs with properties {URL:(contents of linkText)}
            end tell
        end repeat
        set active tab index of destinationWindow to (count of tabs of destinationWindow)
        activate
    end tell
end run
'''

    def __init__(self, *, runner=subprocess.run):
        self.runner = runner

    def open_urls(self, urls: list[str]) -> None:
        if not urls:
            return
        if any(verified_chat_url(url) != url for url in urls):
            raise LaunchError("Refusing an unverified ChatGPT URL")
        try:
            result = self.runner(
                ["/usr/bin/osascript", "-e", self.APPLESCRIPT, *urls],
                text=True, capture_output=True, check=False, timeout=25,
            )
            if result.returncode:
                raise LaunchError("Chrome could not open the requested chat tabs")
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LaunchError("Chrome tab opening failed") from exc


class SessionOpener:
    """One operation across Codex and ChatGPT, with distinct outbound ports."""

    def __init__(self, warp: WarpTabLauncher | None = None,
                 chrome: ChromeTabLauncher | None = None):
        self.warp = warp or WarpTabLauncher()
        self.chrome = chrome or ChromeTabLauncher()

    def open(self, hits: list[SessionHit]) -> OpenResult:
        result = OpenResult(requested=len(hits))
        seen_codex: set[str] = set()
        chrome_urls: list[str] = []
        for hit in hits:
            if hit.provider == "codex":
                try:
                    session_id = _validated_session_id(hit.session_id)
                    if session_id in seen_codex:
                        continue
                    seen_codex.add(session_id)
                    self.warp.open_session(session_id)
                    result.dispatched.append({"provider": "codex", "session_id": session_id,
                                              "destination": "warp-new-tab"})
                except LaunchError as exc:
                    result.errors.append("Codex: " + str(exc))
            elif hit.provider == "chatgpt":
                url = verified_chat_url(hit.url)
                if url:
                    if url not in chrome_urls:
                        chrome_urls.append(url)
                else:
                    result.skipped.append("ChatGPT search suggestion has no verified URL")
            else:
                result.skipped.append("Unknown provider: " + hit.provider)

        if chrome_urls:
            try:
                self.chrome.open_urls(chrome_urls)
                result.dispatched.extend({
                    "provider": "chatgpt", "url": url, "destination": "chrome-new-tab"
                } for url in chrome_urls)
            except LaunchError as exc:
                result.errors.append("ChatGPT: " + str(exc))
        if any(item["provider"] == "codex" for item in result.dispatched):
            try:
                self.warp.reveal()
            except LaunchError as exc:
                result.errors.append("Codex: " + str(exc))
        return result
