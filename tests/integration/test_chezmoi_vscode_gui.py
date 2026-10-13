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


def test_real_chezmoi_diff_opens_valid_vscode_diff_tab(tmp_path):
    """Inspect TabInputTextDiff and text contents via a disposable VS Code extension."""
    code_cli = shutil.which('code')
    assert code_cli
    home = tmp_path / 'home'
    home.mkdir()
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'dot_demo').write_text('expected managed content\n')
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
        fs.writeFileSync(process.env.CHEZMOI_VSCODE_REPORT, JSON.stringify({
          active: tab.isActive,
          left: left.getText(), right: right.getText(),
          leftUri: tab.input.original.toString(),
          rightUri: tab.input.modified.toString(),
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
           'ELECTRON_DISABLE_SECURITY_WARNINGS': 'true'}
    process = subprocess.Popen([
        'chezmoi', '--source', str(source), '--destination', str(home),
        '--config', str(config), 'diff',
    ], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 75
        last = None
        while time.monotonic() < deadline:
            if report.exists():
                last = json.loads(report.read_text())
                if last.get('right') == 'expected managed content\n':
                    break
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise AssertionError(f'chezmoi diff ended before editor state: {stdout} {stderr} {last}')
            time.sleep(0.4)
        else:
            raise AssertionError(f'No valid VS Code diff editor opened: {last}')
        assert last['active']
        assert last['left'] == ''
        assert last['right'] == 'expected managed content\n'
        assert 'null' not in last['leftUri']
        assert last['rightUri'].startswith('file:')
    finally:
        # Only this disposable VS Code profile on an ephemeral CI runner.
        from tests.integration.test_git_review_vscode_gui import stop_isolated_vscode
        stop_isolated_vscode(profile)
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
