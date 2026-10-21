"""Protect profile-based dependency manifests from a second installation policy."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "dependencies/brew/common/cli.Brewfile"

def test_shell_tools_belong_to_common_cli_inventory():
    entries = COMMON.read_text()
    for name in ("chezmoi", "git", "fzf", "zsh-autosuggestions",
                 "zsh-syntax-highlighting", "python", "uv"):
        assert f'brew "{name}"' in entries
    assert not (ROOT / "dependencies/brew/required.Brewfile").exists()

def test_installers_use_one_idempotent_policy():
    shell = (ROOT / "src/shell-setup.sh").read_text()
    apps = (ROOT / "src/apps.sh").read_text()
    assert "install_profile_dependencies common" in shell
    assert 'install_profile_dependencies "$DOTFILES_PROFILE"' in shell
    assert "brew bundle install" not in shell
    assert "install_missing_formula" in apps
    assert "brew list --formula" in apps

def test_ci_skips_hooks_not_arbitrary_package_categories():
    fixture = (ROOT / "tests/support/fresh_home_fixture.sh").read_text()
    assert "apply --exclude scripts --force" in fixture
    for path in [ROOT / "src/shell-setup.sh", *ROOT.glob("home/run_*"),
                 ROOT / ".github/workflows/shell.yml"]:
        assert "DOTFILES_SKIP_OPTIONAL_APPS" not in path.read_text(), path
