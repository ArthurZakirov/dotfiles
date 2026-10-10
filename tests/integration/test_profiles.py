"""Behavioral tests for both machine profiles; low-level setup lives in fixtures."""

import pytest

from tests.support.chezmoi_profile import ChezmoiProfileFixture, RenderedProfile


def test_chezmoi_uses_vscode_for_editing_and_diffs(rendered_profile: RenderedProfile) -> None:
    # GIVEN a rendered machine profile
    # WHEN inspecting its generated chezmoi configuration
    configuration = rendered_profile.config.read_text()

    # THEN VS Code is configured for both operations
    assert '[edit]\n    command = "code"' in configuration
    assert '[diff]\n    command = "code"' in configuration


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
