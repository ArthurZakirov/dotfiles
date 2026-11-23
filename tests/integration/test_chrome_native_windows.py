"""Opt-in local macOS UI regression. Uses disposable profiles and loopback pages."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest


@pytest.mark.skipif(sys.platform != "darwin" or os.environ.get("RUN_CHROME_NATIVE_UI_E2E") != "1",
                    reason="requires an interactive Mac with authorized Chrome Apple Events")
def test_exact_tab_and_new_tab_stay_in_the_owning_process(tmp_path):
    script = Path(__file__).resolve().parents[2] / "home/dot_local/share/dotfiles/browser-use/chrome-tabs.js"
    (tmp_path / "anchor.html").write_text("<title>Anchor</title><h1>Fixture issue</h1><p>Other field</p>")
    (tmp_path / "task.html").write_text("<title>Task</title>")
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(SimpleHTTPRequestHandler, directory=tmp_path))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    anchor, task = origin + "/anchor.html", origin + "/task.html"
    processes = []

    def native(command, *urls):
        return subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", str(script), command, *urls],
                              text=True, capture_output=True, timeout=15)

    def launch(name):
        if name == "first":
            # Configure only this newly created fixture, never a live profile.
            profile = tmp_path / name / "Default"
            profile.mkdir(parents=True)
            (profile / "Preferences").write_text(json.dumps({"browser": {"allow_javascript_apple_events": True}}))
        processes.append(subprocess.Popen(
            ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--user-data-dir=" + str(tmp_path / name),
             "--no-first-run", "--no-default-browser-check", "--disable-sync", anchor],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    def await_lookup(url, duplicate=False):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            result = native("--find-tab", url)
            if duplicate and "found 2" in result.stderr:
                return
            if not duplicate and result.returncode == 0:
                return json.loads(result.stdout)
            time.sleep(0.3)
        pytest.fail(f"Chrome fixture lookup did not settle: {result.stderr}")

    try:
        launch("first")
        first = await_lookup(anchor)
        assert first["pid"] == processes[0].pid
        field = native("--read-tab", anchor, "h1")
        assert field.returncode == 0, field.stderr
        assert json.loads(field.stdout) == {"url": anchor, "title": "Anchor", "text": "Fixture issue"}
        assert native("--read-tab", anchor, "h2").returncode != 0
        assert native("--focus-tab", anchor).returncode == 0
        assert native("--new-tab-in", anchor, task).returncode == 0
        opened = await_lookup(task)
        assert (opened["pid"], opened["windowId"]) == (first["pid"], first["windowId"])
        launch("second")
        await_lookup(anchor, duplicate=True)
        assert "found 2" in native("--read-tab", anchor, "h1").stderr
        assert "found 2" in native("--new-tab-in", anchor, task + "?duplicate").stderr
        assert "found 0" in native("--find-tab", task + "?duplicate").stderr
    finally:
        for proc in processes:
            proc.terminate()
        for proc in processes:
            proc.wait(15)
        server.shutdown()
        server.server_close()
