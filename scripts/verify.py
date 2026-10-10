#!/usr/bin/env python3
"""Render both profiles and exercise real zsh initialization without secrets."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)


with tempfile.TemporaryDirectory() as temporary:
    work = Path(temporary)
    for profile in ("personal", "professional"):
        config = work / f"{profile}.toml"
        base = ["chezmoi", "--source", str(ROOT), "--config", str(config)]
        run(*base, "init", "--promptChoice", f"Mac profile={profile}",
            "--promptString", "GitHub username=ArthurZakirov",
            "--promptString", "Bitwarden Keychain account=bws-macbook-air")
        generated_config = config.read_text()
        assert '[diff]\n    command = "code"' in generated_config
        assert '[edit]\n    command = "code"' in generated_config
        shell = work / f"{profile}.zsh"
        shell.write_text(run(*base, "cat", str(Path.home() / ".zshrc")).stdout)
        run("/bin/zsh", "-n", str(shell))
        installer = work / f"install-{profile}.sh"
        installer.write_text(run(*base, "execute-template", "--file",
            str(ROOT / "home/run_before_10-install-shell.sh.tmpl")).stdout)
        run("/bin/bash", "-n", str(installer))
        backup = work / f"backup-{profile}.sh"
        backup.write_text(run(*base, "execute-template", "--file",
            str(ROOT / "home/run_once_before_00-backup-shell.sh.tmpl")).stdout)
        run("/bin/bash", "-n", str(backup))
        if profile == "professional":
            for forbidden in ("LANGSMITH", "BWS_ACCESS_TOKEN", "bws()", "bws.bitwarden.com"):
                assert forbidden not in shell.read_text() + installer.read_text(), forbidden
        else:
            assert "LANGSMITH_TRACING=true" in shell.read_text()
        # Override Keychain access before loading the real shell: no credential fetches.
        command = 'security() { return 44; }; source "$1"; '
        command += '(( $+functions[_zsh_highlight] && $+functions[_zsh_autosuggest_start] )) || exit 9; '
        command += "[[ \"$PROMPT\" == '%1~${vcs_info_msg_0_} %# ' ]] || exit 10; "
        command += '(( $+functions[compdef] )) || exit 11; '
        if profile == "professional":
            command += '(( ! $+functions[bws] )) || exit 12; '
        result = run("/bin/zsh", "-dfi", "-c", command, "verify", str(shell))
        assert "not found" not in result.stderr, result.stderr
        print(f"{profile}: rendered, syntax checked, interactive startup verified")
