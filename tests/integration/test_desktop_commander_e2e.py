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
    cli = home / '.local/bin/desktop-commander-remote'
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text('#!/bin/sh\nexit 0\n')
    cli.chmod(0o755)
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

    def apply(check=True, allow_interrupt=False):
        run_env = {**env, 'DOTFILES_ALLOW_SERVICE_INTERRUPTION': '1' if allow_interrupt else '0'}
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


def test_untracked_service_requires_explicit_reconciliation(agent):
    home, _, running, apply, calls = agent
    running.touch()
    apply()
    assert running.exists()
    assert not any(c.startswith('bootout ') for c in calls())
    assert not (home / 'Library/Caches/chezmoi' / f'{LABEL}.sha256').exists()
    apply(allow_interrupt=True)
    assert running.exists()
    assert sum(c.startswith('bootout ') for c in calls()) == 1
    assert sum(c.startswith('bootstrap ') for c in calls()) == 1
    assert (home / 'Library/Caches/chezmoi' / f'{LABEL}.sha256').exists()


def test_changed_managed_plist_restart_requires_explicit_permission(agent):
    _, plist, running, apply, calls = agent
    apply()
    plist.write_text(plist.read_text().replace('<key>ProcessType</key>', '<!-- updated -->\n  <key>ProcessType</key>'))
    apply()
    assert running.exists()
    assert not any(c.startswith('bootout ') for c in calls())
    apply(allow_interrupt=True)
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
    npm.write_text("#!/bin/sh\n" "if [ \"$1\" = list ]; then exit 1; fi\n" "printf '%s\\n' \"$*\" >> \"$TEST_NPM_CALLS\"\n" "printf '#!/bin/sh\\nexit 0\\n' > \"$(dirname \"$0\")/desktop-commander\"\n" "chmod +x \"$(dirname \"$0\")/desktop-commander\"\n")
    npm.chmod(0o755)
    if preinstalled:
        cli = fake_bin / 'desktop-commander'
        cli.write_text('#!/bin/sh\nexit 0\n')
        cli.chmod(0o755)
    env = {**os.environ, 'HOME': str(tmp_path), 'PATH': f"{fake_bin}:/usr/bin:/bin",
           'DOTFILES_ROOT': str(root),
           'TEST_NPM_CALLS': str(tmp_path / 'npm-calls')}
    result = subprocess.run([
        '/bin/bash', '-c',
        'source "$1" && source "$DOTFILES_ROOT/src/setup-actions.sh" && install_npm_manifest "$DOTFILES_ROOT/dependencies/npm/personal.txt"', 'test', str(root / 'src/apps.sh'), 'present' if preinstalled else 'missing'
    ], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    link = tmp_path / '.local/bin/desktop-commander-remote'
    assert link.is_symlink()
    assert link.resolve() == (fake_bin / 'desktop-commander').resolve()
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


def test_professional_transition_preserves_then_explicitly_stops_service(agent, profile_factory):
    home, plist, running, apply, calls = agent
    apply()
    professional = profile_factory.render('professional')
    script = profile_factory.render_hook(
        professional.config, 'professional',
        'run_after_20-ensure-desktop-commander-launch-agent.sh.tmpl', 'transition'
    )
    # Use the same fake launchctl state as the personal-profile fixture.
    fake_bin = next(home.parent.glob('bin'))
    env = {**os.environ, 'HOME': str(home),
           'PATH': str(fake_bin) + os.pathsep + os.environ['PATH'],
           'TEST_CALLS': str(home.parent / 'calls'),
           'TEST_RUNNING': str(home.parent / 'running')}
    subprocess.run(['/bin/sh', str(script)], env=env, check=True)
    assert running.exists() and plist.exists()
    assert not any(c.startswith('bootout ') for c in calls())
    env['DOTFILES_ALLOW_SERVICE_INTERRUPTION'] = '1'
    subprocess.run(['/bin/sh', str(script)], env=env, check=True)
    assert not running.exists()
    assert not plist.exists()
    assert not (home / 'Library/Caches/chezmoi' / f'{LABEL}.sha256').exists()
    before = calls()
    subprocess.run(['/bin/sh', str(script)], env=env, check=True)
    assert calls() == before


def test_professional_transition_preserves_unmanaged_service(agent, profile_factory):
    home, plist, running, _, calls = agent
    running.touch()
    professional = profile_factory.render('professional')
    script = profile_factory.render_hook(
        professional.config, 'professional',
        'run_after_20-ensure-desktop-commander-launch-agent.sh.tmpl', 'transition-unmanaged'
    )
    env = {**os.environ, 'HOME': str(home),
           'PATH': str(home.parent / 'bin') + os.pathsep + os.environ['PATH'],
           'TEST_CALLS': str(home.parent / 'calls'),
           'TEST_RUNNING': str(home.parent / 'running')}
    subprocess.run(['/bin/sh', str(script)], env=env, check=True)
    assert running.exists() and plist.exists()
    assert calls() == []


def test_lost_marker_defers_reconciliation_until_explicit_permission(agent):
    home, _, running, apply, calls = agent
    apply()
    marker = home / 'Library/Caches/chezmoi' / f'{LABEL}.sha256'
    marker.unlink()
    apply()
    assert running.exists()
    assert not any(c.startswith('bootout ') for c in calls())
    assert not marker.exists()
    apply(allow_interrupt=True)
    assert sum(c.startswith('bootout ') for c in calls()) == 1
    assert sum(c.startswith('bootstrap ') for c in calls()) == 2
    assert len(marker.read_text().strip()) == 64


def test_missing_cli_keeps_existing_remote_service_intact(agent):
    """A botched first apply cannot bootout the only live remote connection."""
    home, _, running, apply, calls = agent
    running.touch()
    (home / '.local/bin/desktop-commander-remote').unlink()
    result = apply(check=False)
    assert result.returncode != 0
    assert 'executable unavailable' in result.stderr
    assert running.exists()
    assert not calls()
