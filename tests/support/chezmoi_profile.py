"""Render chezmoi profiles without applying anything to the developer's Mac.

The fixture owns subprocess calls, temporary paths and shell verification.
Behavioral tests in test_profiles.py only describe expected outcomes.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional
import os
import subprocess


@dataclass(frozen=True)
class RenderedProfile:
    name: str
    config: Path
    zshrc: Path
    installation_hook: Path
    backup_hook: Path

    @property
    def shell_text(self) -> str:
        return self.zshrc.read_text()


class ChezmoiProfileFixture:
    def __init__(self, repository: Path, scratch_directory: Path):
        self.repository = repository
        self.scratch_directory = scratch_directory

    @staticmethod
    def run(
        *args: str, env: Optional[Mapping[str, str]] = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args, check=True, text=True, capture_output=True, env=env
        )

    def chezmoi(self, config: Path, *args: str) -> str:
        return self.run(
            "chezmoi", "--source", str(self.repository),
            "--config", str(config), *args,
        ).stdout

    def render(self, profile: str) -> RenderedProfile:
        config = self.scratch_directory / f"{profile}.toml"
        self.chezmoi(
            config, "init",
            "--promptChoice", f"Mac profile={profile}",
            "--promptString", "GitHub username=ArthurZakirov",
            "--promptString", "Bitwarden Keychain account=bws-macbook-air",
        )
        zshrc = self.scratch_directory / f"{profile}.zsh"
        zshrc.write_text(self.chezmoi(config, "cat", str(Path.home() / ".zshrc")))

        installation_hook = self.render_hook(
            config, profile, "run_before_10-install-shell.sh.tmpl", "install"
        )
        backup_hook = self.render_hook(
            config, profile, "run_once_before_00-backup-shell.sh.tmpl", "backup"
        )
        return RenderedProfile(profile, config, zshrc, installation_hook, backup_hook)

    def render_hook(self, config: Path, profile: str, template: str, label: str) -> Path:
        output = self.scratch_directory / f"{label}-{profile}.sh"
        output.write_text(self.chezmoi(
            config, "execute-template", "--file",
            str(self.repository / "home" / template),
        ))
        return output

    def validate_shell_syntax(self, rendered: RenderedProfile) -> None:
        for path, interpreter in (
            (rendered.zshrc, "/bin/zsh"),
            (rendered.installation_hook, "/bin/bash"),
            (rendered.backup_hook, "/bin/bash"),
        ):
            self.run(interpreter, "-n", str(path))

    def verify_bws_variables_reach_child_processes(self, rendered: RenderedProfile) -> None:
        # Synthetic CLI output only; no Keychain, network, or real secrets.
        fake_bin = self.scratch_directory / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        fake_bws = fake_bin / "bws"
        fake_bws.write_text('#!/bin/sh\necho \'TEST_BWS_EXPORT="synthetic-value"\'\n')
        fake_bws.chmod(0o755)

        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
        isolated_home = self.scratch_directory / "bws-test-home"
        isolated_home.mkdir(exist_ok=True)
        environment["HOME"] = str(isolated_home)

        # Sourcing the rendered file runs the genuine loading logic.
        shell_check = r"""
security() { return 0; }
source "$1"
[[ "$TEST_BWS_EXPORT" == synthetic-value ]] || exit 20
[[ ! -o allexport ]] || exit 21
/bin/zsh -fc '[[ "$TEST_BWS_EXPORT" == synthetic-value ]]' || exit 22
"""
        self.run("/bin/zsh", "-fc", shell_check, "verify", str(rendered.zshrc),
                 env=environment)

    def start_interactive_shell_without_secrets(self, rendered: RenderedProfile) -> None:
        # Isolate HOME so test startup cannot source the user's .zshrc.local.
        isolated_home = self.scratch_directory / f"home-{rendered.name}"
        isolated_home.mkdir(exist_ok=True)
        (isolated_home / ".oh-my-zsh").symlink_to(
            Path.home() / ".oh-my-zsh", target_is_directory=True
        )
        environment = os.environ.copy()
        environment["HOME"] = str(isolated_home)

        # Override Keychain lookup, never fetch a Bitwarden token or call bws.
        shell_check = r"""
security() { return 44; }
source "$1"
(( $+functions[_zsh_highlight] && $+functions[_zsh_autosuggest_start] )) || exit 9
[[ "$PROMPT" == '%1~${vcs_info_msg_0_} %# ' ]] || exit 10
(( $+functions[compdef] )) || exit 11
"""
        if rendered.name == "professional":
            shell_check += '(( ! $+functions[bws] )) || exit 12\n'

        result = self.run(
            "/bin/zsh", "-dfi", "-c", shell_check,
            "verify", str(rendered.zshrc), env=environment,
        )
        if "not found" in result.stderr:
            raise AssertionError(result.stderr)
