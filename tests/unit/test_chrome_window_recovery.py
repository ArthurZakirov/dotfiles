"""Discovery and native selection boundaries, independent of OS consent dialogs."""
import importlib.util
from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANAGED = ROOT / "home/dot_local/share/dotfiles/browser-use"
spec = importlib.util.spec_from_file_location("signed_in", MANAGED / "signed-in.py")
signed_in = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signed_in)


@pytest.mark.parametrize(("ports", "status", "payload", "expected"), [
    ([9222], 404, "", (9222, "ws://127.0.0.1:9222/devtools/browser")),
    ([61234], 404, "", None),
    ([61234], 200, '{"webSocketDebuggerUrl":"ws://127.0.0.1:61234/devtools/browser/test"}',
     (61234, "ws://127.0.0.1:61234/devtools/browser/test")),
    ([9222], 200, '{"webSocketDebuggerUrl":"ws://other-host:9222/devtools/browser/test"}', None),
    ([9222], 302, "", None),
    ([], 404, "", None),
])
def test_discovery_only_accepts_a_verified_local_endpoint(ports, status, payload, expected):
    response = Mock(status=status)
    response.read.return_value = payload.encode()
    with patch.object(signed_in, "listener_ports", return_value=ports) as listeners, \
            patch.object(signed_in.http.client, "HTTPConnection") as connection:
        connection.return_value.getresponse.return_value = response
        if expected is None:
            with pytest.raises(RuntimeError, match="no unique"):
                signed_in.published_endpoint(345)
        else:
            assert signed_in.published_endpoint(345) == expected
        listeners.assert_called_once_with(345)


def test_native_selection_across_processes_and_windows():
    # JXA objects are substituted only for this selection test. No UI is touched.
    js = (MANAGED / "chrome-tabs.js").read_text() + """
const assert = require('node:assert/strict');
const target = 'https://example.com/task';
const tab = (url, i) => ({id: () => i + 1, url: () => url});
const win = (mode, urls) => ({id: () => 123, mode: () => mode, tabs: () => urls.map(tab)});
const windows = {11:[win('normal', [target + '/']),win('incognito', [target])],
                 22:[win('normal', [target])]};
const app = pid => ({windows: () => windows[pid]});
const lookup = () => locate([11,22], app, target);
assert.equal(lookup().pid, 22);
windows[11].push(win('normal', [target]));
assert.throws(lookup, /found 2/);
windows[11].pop();
windows[22] = [];
assert.throws(lookup, /found 0/);
"""
    subprocess.run(["node", "-e", js], check=True)
