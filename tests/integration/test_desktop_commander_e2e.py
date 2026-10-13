"""Exercise rendered Desktop Commander LaunchAgent with an isolated HOME.

Actual chezmoi renders and the actual shell hook run; only macOS launchctl,
plutil and shasum are substituted, so tests never affect a real login session.
"""
import os
from pathlib import Path
import subprocess

import pytest


LABEL = 'com.arthur.desktop-commander-remote'


def test_personal_plist_renders_expected_service(profile_factory):
    rendered = profile_factory.render('personal')
    plist = profile_factory.chezmoi(
        rendered.config, 'cat', str(Path.home() / 'Library/LaunchAgents' / f'{LABEL}.plist')
    )
    for expected in ('<string>remote</string>', '<key>RunAtLoad</key>',
                     '<key>KeepAlive</key>', '<true/>', '<key>StandardErrorPath</key>',
                     '<key>StandardOutPath</key>', '<string>com.arthur.desktop-commander-remote</string>'):
        assert expected in plist
    assert 'desktop-commander' in plist
    assert '{{' not in plist


@pytest.fixture
def agent(tmp_path, profile_factory):
    rendered = profile_factory.render('personal')
    home = tmp_path / 'home'
    home.mkdir()
    plist = home / 'Library/LaunchAgents' / f'{LABEL}.plist'
    assert not plist.exists()
    assert not (home / 'Library').exists()
    provision = subprocess.run([
        'chezmoi', '--source', str(profile_factory.repository / 'home'),
        '--config', str(rendered.config), '--destination', str(home),
        'apply', '--exclude', 'scripts', '--force',
    ], capture_output=True, text=True)
    assert provision.returncode == 0, provision.stderr
    assert plist.exists()
    script = profile_factory.render_hook(
        rendered.config, 'personal', 'run_after_20-ensure-desktop-commander-launch-agent.sh.tmpl', 'agent'
    )
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    # Fake launchctl persists state across calls, as launchd does.
    launchctl = bin_dir / 'launchctl'
    launchctl.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$TEST_CALLS"
case "$1" in
 print) [ -e "$TEST_RUNNING" ] ;;
 bootstrap) touch "$TEST_RUNNING" ;;
 bootout) rm -f "$TEST_RUNNING" ;;
 *) exit 9 ;;
esac
''')
    launchctl.chmod(0o755)
    # plist validation remains real; only path to launchctl is stubbed.
    env = {**os.environ, 'HOME': str(home),
           'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'],
           'TEST_CALLS': str(tmp_path / 'calls'),
           'TEST_RUNNING': str(tmp_path / 'running')}

    def apply(optional_skip=False, check=True):
        run_env = {**env, 'DOTFILES_SKIP_OPTIONAL_APPS': '1' if optional_skip else '0'}
        return subprocess.run(['/bin/sh', str(script)], env=run_env, text=True,
                              capture_output=True, check=check)

    def calls():
        return (tmp_path / 'calls').read_text().splitlines() if (tmp_path / 'calls').exists() else []

    return home, plist, tmp_path / 'running', apply, calls


def test_first_apply_bootstraps_and_writes_marker(agent):
    home, plist, running, apply, calls = agent
    apply()
    assert running.exists()
    assert sum(call.startswith('bootstrap ') for call in calls()) == 1
    marker = home / 'Library/Caches/chezmoi' / f'{LABEL}.sha256'
    assert len(marker.read_text().strip()) == 64


def test_repeated_apply_does_not_restart_service(agent):
    _, _, _, apply, calls = agent
    apply()
    first = list(calls())
    apply()
    assert calls().count(next(c for c in first if c.startswith('bootstrap '))) == 1
    assert not any(c.startswith('bootout ') for c in calls())


def test_existing_unmanaged_agent_is_adopted_without_interruption(agent):
    home, _, running, apply, calls = agent
    running.touch()
    apply()
    assert running.exists()
    assert not any(c.startswith(('bootout ', 'bootstrap ')) for c in calls())
    assert (home / 'Library/Caches/chezmoi' / f'{LABEL}.sha256').exists()


def test_changed_managed_plist_triggers_one_restart(agent):
    _, plist, running, apply, calls = agent
    apply()
    plist.write_text(plist.read_text().replace('<key>ProcessType</key>', '<!-- updated -->\n  <key>ProcessType</key>'))
    apply()
    assert running.exists()
    assert sum(c.startswith('bootout ') for c in calls()) == 1
    assert sum(c.startswith('bootstrap ') for c in calls()) == 2
    apply()
    assert sum(c.startswith('bootout ') for c in calls()) == 1


def test_stopped_agent_is_recovered(agent):
    _, _, running, apply, calls = agent
    apply()
    running.unlink()
    apply()
    assert running.exists()
    assert sum(c.startswith('bootstrap ') for c in calls()) == 2


def test_optional_apps_skip_does_not_start_agent(agent):
    home, _, running, apply, calls = agent
    apply(optional_skip=True)
    assert not running.exists()
    assert not calls()
    assert not (home / 'Library/Caches/chezmoi' / f'{LABEL}.sha256').exists()


def test_invalid_plist_does_not_touch_running_service(agent):
    _, plist, running, apply, calls = agent
    running.touch()
    plist.write_text('not a plist')
    result = apply(check=False)
    assert result.returncode != 0
    assert running.exists()
    assert not calls()


@pytest.mark.parametrize('preinstalled', [False, True])
def test_npm_installer_handles_missing_and_existing_cli(tmp_path, preinstalled):
    """Run the production installer against an isolated npm/CLI executable."""
    root = Path(__file__).resolve().parents[2]
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    npm = fake_bin / 'npm'
    npm.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_NPM_CALLS"\n')
    npm.chmod(0o755)
    if preinstalled:
        cli = fake_bin / 'desktop-commander'
        cli.write_text('#!/bin/sh\nexit 0\n')
        cli.chmod(0o755)
    env = {**os.environ, 'PATH': f"{fake_bin}:{os.environ['PATH']}",
           'TEST_NPM_CALLS': str(tmp_path / 'npm-calls')}
    result = subprocess.run([
        '/bin/bash', '-c',
        'source "$1"; if [ "$2" = missing ]; then command() { if [ "$1" = -v ] && [ "$2" = desktop-commander ]; then return 1; fi; builtin command "$@"; }; fi; install_desktop_commander_cli', 'test', str(root / 'src/apps.sh'), 'present' if preinstalled else 'missing'
    ], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    log = tmp_path / 'npm-calls'
    if preinstalled:
        assert not log.exists()
    else:
        assert log.read_text().splitlines() == [
            'install --global @wonderwhy-er/desktop-commander'
        ]


@pytest.mark.parametrize('profile', ['personal', 'professional'])
def test_fresh_home_chezmoi_apply_creates_plist_before_launch(profile, tmp_path, profile_factory):
    """Start with no Library or plist; apply actual chezmoi-managed files.

    Skip installer hooks on a developer Mac: lifecycle execution is covered
    separately with isolated launchctl, and full provisioning belongs to CI.
    """
    rendered = profile_factory.render(profile)
    home = tmp_path / 'fresh-home'
    home.mkdir()
    plist = home / 'Library/LaunchAgents' / f'{LABEL}.plist'
    assert not (home / 'Library').exists()
    assert not plist.exists()
    assert not (home / 'Library/Caches/chezmoi').exists()
    assert not (home / '.local/bin/desktop-commander').exists()

    result = subprocess.run([
        'chezmoi', '--source', str(profile_factory.repository / 'home'),
        '--config', str(rendered.config), '--destination', str(home),
        'apply', '--exclude', 'scripts', '--force',
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if profile == 'personal':
        assert plist.is_file()
        assert subprocess.run(['plutil', '-lint', str(plist)], capture_output=True).returncode == 0
        assert '<string>remote</string>' in plist.read_text()
    else:
        assert not plist.exists()
    assert not (home / 'Library/Caches/chezmoi').exists()
