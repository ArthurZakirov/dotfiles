"""Behavioral tests for both machine profiles; low-level setup lives in fixtures."""

import os
import shlex

import pytest

from tests.support.chezmoi_profile import ChezmoiProfileFixture, RenderedProfile
from tests.support.rendered_snapshots import assert_snapshots_match


def test_complete_render_matches_reviewed_snapshots(
    rendered_profile: RenderedProfile, profile_factory: ChezmoiProfileFixture
) -> None:
    # GIVEN committed full renders of both machine profiles
    # WHEN chezmoi renders the same files on this machine
    # THEN every byte matches the reviewed, path-normalized snapshots
    assert_snapshots_match(rendered_profile, profile_factory.repository)


def test_chezmoi_uses_vscode_for_editing_and_diffs(rendered_profile: RenderedProfile) -> None:
    # GIVEN a rendered machine profile
    # WHEN inspecting its generated chezmoi configuration
    configuration = rendered_profile.config.read_text()

    # THEN VS Code is configured for both operations
    assert '[edit]\n    command = "code"' in configuration
    assert '[diff]\n    pager = ""\n    command = "/bin/bash"' in configuration
    assert 'executable_chezmoi-code-diff' in configuration


def test_shell_and_installation_hooks_have_valid_syntax(
    rendered_profile: RenderedProfile, profile_factory: ChezmoiProfileFixture
) -> None:
    # GIVEN a rendered profile and its lifecycle hooks
    # WHEN validating their syntax
    # THEN all files parse without errors
    profile_factory.validate_shell_syntax(rendered_profile)


@pytest.mark.parametrize(
    ("profile", "expected_integrations"),
    [
        ("personal", True),
        ("professional", False),
    ],
)
def test_profile_integrations_are_scoped(
    profile: str, expected_integrations: bool,
    profile_factory: ChezmoiProfileFixture,
) -> None:
    # GIVEN a personal or professional profile
    rendered = profile_factory.render(profile)

    # WHEN inspecting the rendered configuration
    scripts = rendered.shell_text + rendered.installation_hook.read_text()

    # THEN personal integrations exist only on personal Macs
    integrations = ("LANGSMITH_TRACING=true", "bws()")
    for integration in integrations:
        assert (integration in scripts) is expected_integrations
    if not expected_integrations:
        for forbidden in ("BWS_ACCESS_TOKEN", "bws.bitwarden.com"):
            assert forbidden not in scripts


def test_bitwarden_keys_are_exported_to_child_processes(
    profile_factory: ChezmoiProfileFixture,
) -> None:
    # GIVEN a personal profile and synthetic Bitwarden env assignments
    rendered = profile_factory.render("personal")

    # WHEN sourcing the personal shell configuration
    # THEN a child zsh inherits the variables and allexport is restored
    profile_factory.verify_bws_variables_reach_child_processes(rendered)


def test_interactive_shell_starts_without_secrets(
    rendered_profile: RenderedProfile, profile_factory: ChezmoiProfileFixture
) -> None:
    # GIVEN a rendered profile with isolated HOME and stubbed Keychain access
    # WHEN launching interactive zsh
    # THEN completion, prompt, and plugins initialize correctly
    profile_factory.start_interactive_shell_without_secrets(rendered_profile)


def test_desktop_commander_launch_agent_is_personal_only(
    profile_factory: ChezmoiProfileFixture,
) -> None:
    """The plist must not be managed on professional machines."""
    for profile, expected in (("personal", True), ("professional", False)):
        rendered = profile_factory.render(profile)
        entries = profile_factory.chezmoi(rendered.config, "managed", "--include", "files")
        assert ("Library/LaunchAgents/com.arthur.desktop-commander-remote.plist" in entries) is expected
        hook = profile_factory.render_hook(
            rendered.config, profile,
            "run_after_20-ensure-desktop-commander-launch-agent.sh.tmpl",
            "desktop-commander",
        )
        profile_factory.run("/bin/sh", "-n", str(hook))
        assert ("launchctl bootstrap" in hook.read_text()) is expected


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_peekaboo_skill_hook_is_rendered_and_safe_to_skip(
    profile: str, profile_factory: ChezmoiProfileFixture, tmp_path,
) -> None:
    rendered = profile_factory.render(profile)
    hook = profile_factory.render_hook(
        rendered.config, profile,
        "run_after_40-ensure-peekaboo-skill.sh.tmpl", "peekaboo",
    )
    content = hook.read_text()
    assert "ensure_agent_skill peekaboo openclaw/Peekaboo" in content
    assignment = next(line for line in content.splitlines() if line.startswith("DOTFILES_ROOT="))
    assert shlex.split(assignment) == [f"DOTFILES_ROOT={profile_factory.repository}"]
    assert 'source "$DOTFILES_ROOT/src/homebrew.sh"' in content
    assert content.index("configure_homebrew") < content.index("command -v peekaboo")
    assert 'source "$DOTFILES_ROOT/src/agent-skills.sh"' in content
    profile_factory.run("/bin/bash", "-n", str(hook))
    assert (profile_factory.repository / "home/run_after_40-ensure-peekaboo-skill.sh.tmpl").stat().st_mode & 0o111

    # Headless profile rendering must not install tools or contact GitHub.
    profile_factory.run(
        "/bin/bash", str(hook),
        env={**os.environ, "HOME": str(tmp_path), "DOTFILES_SKIP_OPTIONAL_APPS": "1"},
    )
    assert not (tmp_path / ".agents").exists()


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_agent_browser_hook_renders_for_both_profiles(
    profile: str, profile_factory: ChezmoiProfileFixture, tmp_path,
) -> None:
    rendered = profile_factory.render(profile)
    hook = profile_factory.render_hook(
        rendered.config, profile,
        "run_after_50-ensure-agent-browser.sh.tmpl", "agent-browser",
    )
    content = hook.read_text()
    assignment = next(line for line in content.splitlines() if line.startswith("DOTFILES_ROOT="))
    assert shlex.split(assignment) == [f"DOTFILES_ROOT={profile_factory.repository}"]
    assert 'source "$DOTFILES_ROOT/src/agent-skills.sh"' in content
    assert 'source "$DOTFILES_ROOT/src/homebrew.sh"' in content
    assert 'ensure_agent_skill agent-browser vercel-labs/agent-browser' in content
    assert 'for binary in agent-browser npm npx skills; do' in content
    assert 'agent-browser install' in content
    profile_factory.run("/bin/bash", "-n", str(hook))
    profile_factory.run(
        "/bin/bash", str(hook),
        env={**os.environ, "HOME": str(tmp_path), "DOTFILES_SKIP_OPTIONAL_APPS": "1"},
    )
    assert not (tmp_path / ".agents").exists()


@pytest.mark.parametrize("profile", ["personal", "professional"])
def test_preapply_backup_hook_uses_invoking_chezmoi_paths(
    profile: str, profile_factory: ChezmoiProfileFixture,
) -> None:
    rendered = profile_factory.render(profile)
    hook = profile_factory.render_hook(
        rendered.config, profile,
        "run_before_01-snapshot-existing-managed.sh.tmpl", "backup-managed",
    )
    source = profile_factory.repository / "home"
    assert f'{source}' in hook.read_text()
    assert 'snapshot_existing_managed' in hook.read_text()
    profile_factory.run("/bin/bash", "-n", str(hook))
