"""Real VS Code editor-state verification on an ephemeral Linux Xvfb CI runner."""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / 'home/dot_local/bin/executable_chezmoi-code-diff'
pytestmark = pytest.mark.skipif(
    not (os.environ.get('CI') == 'true'
         and os.environ.get('RUN_VSCODE_GUI_E2E') == '1'
         and sys.platform.startswith('linux')),
    reason='Requires isolated Linux/Xvfb CI and real VS Code',
)


@pytest.mark.parametrize("scenario", ["new-file", "hammerspoon-existing-symlink"])
def test_real_chezmoi_diff_opens_valid_vscode_diff_tab(tmp_path, scenario):
    """Verify real diff editor documents for new files and Hammerspoon upgrades."""
    code_cli = shutil.which('code')
    assert code_cli
    home = tmp_path / 'home'
    home.mkdir()
    source = tmp_path / 'source'
    source.mkdir()
    if scenario == "new-file":
        (source / 'dot_demo').write_text('expected managed content\n')
        expected_left, expected_right = '', 'expected managed content\n'
    else:
        # Existing Macs can have an arbitrary and even dangling Hammerspoon
        # symlink. Chezmoi compares it with /dev/null during a directory upgrade.
        shutil.copytree(ROOT / 'home/dot_hammerspoon', source / 'dot_hammerspoon')
        installed = home / '.hammerspoon'
        installed.mkdir()
        old_bin = tmp_path / 'unrelated-hammerspoon/bin'
        (installed / 'bin').symlink_to(old_bin, target_is_directory=True)
        expected_left = f'Symbolic link -> {old_bin}\n'
        expected_right = ''
    config = tmp_path / 'chezmoi.toml'
    config.write_text('[diff]\ncommand = "/bin/bash"\n'
                      f'args = ["{ADAPTER}"]\n')
    profile = tmp_path / 'vscode-profile'
    extensions = tmp_path / 'extensions'
    extensions.mkdir()
    observer = tmp_path / 'observer'
    observer.mkdir()
    report = tmp_path / 'diff-state.json'
    (observer / 'package.json').write_text(json.dumps({
        'name': 'chezmoi-diff-observer', 'displayName': 'Diff Observer',
        'version': '0.0.1', 'publisher': 'local-test',
        'engines': {'vscode': '^1.90.0'},
        'main': './extension.js', 'activationEvents': ['*'],
    }))
    (observer / 'extension.js').write_text(r'''
const vscode = require('vscode');
const fs = require('fs');
async function check() {
  for (const group of vscode.window.tabGroups.all) {
    for (const tab of group.tabs) {
      if (!(tab.input instanceof vscode.TabInputTextDiff)) continue;
      try {
        const left = await vscode.workspace.openTextDocument(tab.input.original);
        const right = await vscode.workspace.openTextDocument(tab.input.modified);
        const leftText = left.getText();
        const rightText = right.getText();
        // Prefer the intended diff when chezmoi offers several files.
        if (leftText !== process.env.CHEZMOI_EXPECTED_LEFT ||
            rightText !== process.env.CHEZMOI_EXPECTED_RIGHT) continue;
        fs.writeFileSync(process.env.CHEZMOI_VSCODE_REPORT, JSON.stringify({
          active: tab.isActive,
          left: leftText, right: rightText,
          leftUri: tab.input.original.toString(),
          rightUri: tab.input.modified.toString(),
          leftFileExists: fs.existsSync(tab.input.original.fsPath),
          rightFileExists: fs.existsSync(tab.input.modified.fsPath),
          name: tab.label,
        }));
      } catch (e) {
        fs.writeFileSync(process.env.CHEZMOI_VSCODE_REPORT,
          JSON.stringify({error: String(e)}));
      }
    }
  }
}
function activate(context) {
  const timer = setInterval(() => { void check(); }, 400);
  context.subscriptions.push({dispose: () => clearInterval(timer)});
  void check();
}
exports.activate = activate;
exports.deactivate = () => {};
''')
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    wrapper = bindir / 'code'
    wrapper.write_text('#!/bin/sh\n'
                       f'exec "{code_cli}" --no-sandbox --disable-gpu '
                       '--disable-workspace-trust '
                       f'--user-data-dir "{profile}" '
                       f'--extensions-dir "{extensions}" '
                       f'--extensionDevelopmentPath "{observer}" "$@"\n')
    wrapper.chmod(0o755)
    env = {**os.environ, 'HOME': str(home),
           'PATH': f'{bindir}:{os.environ["PATH"]}',
           'CHEZMOI_VSCODE_REPORT': str(report),
           'CHEZMOI_EXPECTED_LEFT': expected_left,
           'CHEZMOI_EXPECTED_RIGHT': expected_right,
           'CHEZMOI_CODE_DIFF_CACHE': str(tmp_path / 'snapshots'),
           'ELECTRON_DISABLE_SECURITY_WARNINGS': 'true'}
    process = subprocess.Popen([
        'chezmoi', '--source', str(source), '--destination', str(home),
        '--config', str(config), 'diff',
        *(['--recursive', str(home / '.hammerspoon')] if scenario != 'new-file' else []),
    ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    try:
        deadline = time.monotonic() + 75
        last = None
        while time.monotonic() < deadline:
            if report.exists():
                last = json.loads(report.read_text())
                if last.get('left') == expected_left and last.get('right') == expected_right:
                    break
            if process.poll() is not None:
                raise AssertionError(f'chezmoi diff ended before editor state: exit={process.returncode}, state={last}')
            time.sleep(0.4)
        else:
            raise AssertionError(f'No valid VS Code diff editor opened: {last}')
        assert last['active']
        assert last['left'] == expected_left
        assert last['right'] == expected_right
        assert last['leftFileExists']
        assert last['rightFileExists']
        assert 'null' not in last['leftUri']
        assert last['rightUri'].startswith('file:')
    finally:
        # Only this disposable VS Code profile on an ephemeral CI runner.
        from tests.integration.test_git_review_vscode_gui import stop_isolated_vscode
        stop_isolated_vscode(profile)
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
