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
        expected_pairs = [('', 'expected managed content\n')]
    else:
        # Existing Macs can have an arbitrary and even dangling Hammerspoon
        # symlink. Chezmoi compares it with /dev/null during a directory upgrade.
        shutil.copytree(ROOT / 'home/dot_hammerspoon', source / 'dot_hammerspoon')
        installed = home / '.hammerspoon'
        installed.mkdir()
        old_config = tmp_path / 'unrelated-hammerspoon'
        modules = old_config / 'modules'
        modules.mkdir(parents=True)
        (modules / 'spaces.lua').write_text('-- previous space behavior\n')
        (modules / 'chatgpt.lua').write_text('-- previous ChatGPT behavior\n')
        old_bin = old_config / 'bin'
        (installed / 'bin').symlink_to(old_bin, target_is_directory=True)
        (installed / 'modules').symlink_to(modules, target_is_directory=True)
        expected_pairs = [
            (f'Symbolic link -> {old_bin}\n', ''),
            ('-- previous space behavior\n',
             (ROOT / 'home/dot_hammerspoon/modules/spaces.lua').read_text()),
            ('-- previous ChatGPT behavior\n',
             (ROOT / 'home/dot_hammerspoon/modules/chatgpt.lua').read_text()),
        ]
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
  const report = { activated: true, tabs: [] };
  for (const group of vscode.window.tabGroups.all) {
    for (const tab of group.tabs) {
      if (!(tab.input instanceof vscode.TabInputTextDiff)) continue;
      try {
        const left = await vscode.workspace.openTextDocument(tab.input.original);
        const right = await vscode.workspace.openTextDocument(tab.input.modified);
        report.tabs.push({
          active: tab.isActive,
          left: left.getText(), right: right.getText(),
          leftUri: tab.input.original.toString(),
          rightUri: tab.input.modified.toString(),
          leftFileExists: fs.existsSync(tab.input.original.fsPath),
          rightFileExists: fs.existsSync(tab.input.modified.fsPath),
          name: tab.label,
        });
      } catch (error) {
        report.tabs.push({error: String(error), name: tab.label});
      }
    }
  }
  const target = process.env.CHEZMOI_VSCODE_REPORT;
  fs.writeFileSync(target + '.pending', JSON.stringify(report));
  fs.renameSync(target + '.pending', target);
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
                       'printf "%s\\n" "$@" >> "$CHEZMOI_EDITOR_LAUNCH_LOG"\n'
                       f'exec "{code_cli}" --no-sandbox --disable-gpu '
                       '--disable-workspace-trust '
                       f'--user-data-dir "{profile}" '
                       f'--extensions-dir "{extensions}" "$@"\n')
    wrapper.chmod(0o755)
    env = {**os.environ, 'HOME': str(home),
           'PATH': f'{bindir}:{os.environ["PATH"]}',
           'CHEZMOI_VSCODE_REPORT': str(report),
           'CHEZMOI_CODE_DIFF_CACHE': str(tmp_path / 'snapshots'),
           'ELECTRON_DISABLE_SECURITY_WARNINGS': 'true'}
    log_path = tmp_path / 'chezmoi-stderr.log'
    launch_log = tmp_path / 'editor-launches.log'
    env['CHEZMOI_EDITOR_LAUNCH_LOG'] = str(launch_log)
    stderr_log = log_path.open('w')
    # Start the observer once, in the exact isolated window all diff tabs
    # should use. Repeated --extensionDevelopmentPath invocations accidentally
    # launched distinct windows, leaving the observer with zero diff tabs.
    bootstrap = subprocess.Popen([
        str(wrapper), '--extensionDevelopmentPath', str(observer),
        '--new-window', str(home),
    ], env=env, stdout=subprocess.DEVNULL, stderr=stderr_log, text=True)
    process = None
    try:
        startup_deadline = time.monotonic() + 45
        while time.monotonic() < startup_deadline:
            if report.exists() and json.loads(report.read_text()).get('activated'):
                break
            time.sleep(0.3)
        else:
            raise AssertionError(f'VS Code observer did not activate; stderr={log_path.read_text()}')

        process = subprocess.Popen([
            'chezmoi', '--source', str(source), '--destination', str(home),
            '--config', str(config), 'diff',
            *(['--recursive', str(home / '.hammerspoon')] if scenario != 'new-file' else []),
        ], env=env, stdout=subprocess.DEVNULL, stderr=stderr_log, text=True)
        deadline = time.monotonic() + 75
        last = None
        matching = []
        while time.monotonic() < deadline:
            if report.exists():
                last = json.loads(report.read_text())
                tabs = last.get('tabs', [])
                matching = [
                    next((tab for tab in tabs
                          if tab.get('left') == left and tab.get('right') == right), None)
                    for left, right in expected_pairs
                ]
                if all(tab is not None for tab in matching):
                    break
            if process.poll() is not None and process.returncode != 0:
                break
            time.sleep(0.4)
        if not matching or any(tab is None for tab in matching):
            raise AssertionError(
                f'Expected {len(expected_pairs)} simultaneous VS Code diff tabs: '
                f'report={last}; chezmoi_exit={process.poll()}; '
                f'editor_invocations={launch_log.read_text() if launch_log.exists() else None}; '
                f'chezmoi_stderr={log_path.read_text()}'
            )
        for tab in matching:
            assert tab['leftFileExists']
            assert tab['rightFileExists']
            assert 'null' not in tab['leftUri']
            assert tab['rightUri'].startswith('file:')
        assert any(tab['active'] for tab in matching)
    finally:
        stderr_log.close()
        # Only this disposable VS Code profile on an ephemeral CI runner.
        from tests.integration.test_git_review_vscode_gui import stop_isolated_vscode
        stop_isolated_vscode(profile)
        for child in (process, bootstrap):
            if child is None:
                continue
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
