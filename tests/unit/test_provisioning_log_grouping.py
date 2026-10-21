"""Regression coverage for readable, non-recursive chezmoi lifecycle output."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def hook(name):
    return (ROOT / "home" / name).read_text()

def test_no_recursive_chezmoi_source_path_in_after_hooks():
    for path in (ROOT / "home").glob("run_after_*"):
        assert "chezmoi source-path" not in path.read_text(), path.name

def test_related_tools_share_sections():
    assert 'dotfiles_section "AGENT TOOLING"' in hook("run_after_40-ensure-peekaboo-skill.sh.tmpl")
    assert 'dotfiles_subsection "NPX SKILLS / AGENT BROWSER"' in hook("run_after_50-ensure-agent-browser.sh.tmpl")
    assert 'dotfiles_subsection "BROWSER RUNTIME"' in hook("run_after_50-ensure-agent-browser.sh.tmpl")
    assert 'dotfiles_section "MACOS CONFIGURATION"' in hook("run_after_30-apply-macos-shortcuts.sh.tmpl")
    assert 'RAYCAST' in hook("run_after_60-raycast-onboarding.sh")
    assert 'dotfiles_section "BACKGROUND SERVICES"' in hook("run_after_20-ensure-desktop-commander-launch-agent.sh.tmpl")

def test_existing_raycast_marker_still_reports_status():
    script = hook("run_after_60-raycast-onboarding.sh")
    assert 'Raycast: Repository Manager onboarding already offered.' in script

def test_hammerspoon_apply_does_not_attempt_toolchain_installation():
    script = hook("run_after_30-ensure-hammerspoon.sh")
    assert '$swift_setup' not in script
    assert "chezmoi source-path" not in script
