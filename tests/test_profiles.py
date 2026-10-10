"""Readable behavior tests for rendered personal and professional profiles."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests.support.chezmoi_profile import ChezmoiProfileFixture


class TestProfileRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = TemporaryDirectory(prefix="dotfiles-profile-tests-")
        cls.fixture = ChezmoiProfileFixture(
            Path(__file__).resolve().parents[1], Path(cls.temporary.name)
        )
        cls.personal = cls.fixture.render("personal")
        cls.professional = cls.fixture.render("professional")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_chezmoi_uses_vscode_for_editing_and_diffs(self) -> None:
        # GIVEN both machine profiles have been rendered
        for profile in (self.personal, self.professional):
            with self.subTest(profile=profile.name):
                # WHEN inspecting the generated chezmoi configuration
                config_text = profile.config.read_text()

                # THEN VS Code is configured for edit and diff operations
                self.assertIn('[edit]\n    command = "code"', config_text)
                self.assertIn('[diff]\n    command = "code"', config_text)

    def test_shell_and_installation_hooks_have_valid_syntax(self) -> None:
        # GIVEN rendered zshrc and lifecycle hooks for each profile
        for profile in (self.personal, self.professional):
            with self.subTest(profile=profile.name):
                # WHEN checking all scripts with their respective shells
                # THEN each script parses successfully
                self.fixture.validate_shell_syntax(profile)

    def test_personal_profile_enables_personal_integrations(self) -> None:
        # GIVEN a personal Mac profile
        profile = self.personal

        # WHEN reading its rendered shell configuration
        shell = profile.shell_text

        # THEN LangSmith and the Bitwarden wrapper are available
        self.assertIn("LANGSMITH_TRACING=true", shell)
        self.assertIn("bws()", shell)

    def test_professional_profile_excludes_personal_integrations(self) -> None:
        # GIVEN a professional Mac profile
        profile = self.professional

        # WHEN inspecting the rendered shell and installation hook
        scripts = profile.shell_text + profile.installation_hook.read_text()

        # THEN neither Bitwarden nor LangSmith configuration appears
        for forbidden in ("LANGSMITH", "BWS_ACCESS_TOKEN", "bws()", "bws.bitwarden.com"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, scripts)

    def test_both_profiles_initialize_an_interactive_shell(self) -> None:
        # GIVEN both rendered profiles and a stubbed Keychain command
        for profile in (self.personal, self.professional):
            with self.subTest(profile=profile.name):
                # WHEN starting zsh with the rendered configuration
                # THEN completion, prompt and shell plugins initialize
                self.fixture.start_interactive_shell_without_secrets(profile)


def main() -> None:
    unittest.main(module=__name__, verbosity=2)


if __name__ == "__main__":
    main()
