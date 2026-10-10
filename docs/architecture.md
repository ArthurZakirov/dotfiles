# How it works

[← README](../README.md)

**Chezmoi** is the native entry point. It discovers `<GitHub username>/dotfiles`, clones the repository, generates a machine-local configuration, and applies the declared files. **Git** carries updates between Macs, while **Homebrew** installs dependencies. The supported operating system is macOS.

## Components and order

| File | Description |
|---|---|
| [Official chezmoi installer](https://www.chezmoi.io/install/) | Installs chezmoi and forwards `init --apply USERNAME`; no custom bootstrap downloader. |
| [`home/.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) | Prompts for profile, GitHub username, and optional Bitwarden Keychain account; configures VS Code integration. Credentials stay outside Git. |
| [`home/run_once_before_00-backup-shell.sh.tmpl`](../home/run_once_before_00-backup-shell.sh.tmpl) | Backs up an existing `.zshrc` before the managed version is applied. |
| [`home/run_before_10-install-shell.sh.tmpl`](../home/run_before_10-install-shell.sh.tmpl) | Runs the shell installation process. |
| [`src/shell-setup.sh`](../src/shell-setup.sh) | Reusable shell, editor, and profile installers; selects personal or professional integrations. |
| [`src/homebrew.sh`](../src/homebrew.sh) | Installs Homebrew if missing and configures its shell environment. |
| [`Brewfile`](../Brewfile) | Declares Homebrew packages without locking exact package versions. |
| [`home/.chezmoidata.toml`](../home/.chezmoidata.toml) | Stores shared settings including the pinned Oh My Zsh revision. |
| [`home/dot_zshrc.tmpl`](../home/dot_zshrc.tmpl) | Renders shell history, completion, prompt, Git helpers, fzf, and plugins. |
| [`home/.chezmoitemplates/personal.zsh`](../home/.chezmoitemplates/personal.zsh) | Adds personal-only integrations such as Bitwarden Secrets Manager CLI and LangSmith. |

The installation hook runs before the managed `~/.zshrc` is applied, so required shell dependencies are available on first shell startup. The backup hook is run-once; the installer hook is idempotent and checks dependencies on subsequent applies.

## Synchronization and safety

Changes committed and pushed on one Mac are available to the other via `chezmoi update`, an **explicit** pull-and-apply operation. Machine-local profile settings stay in that machine's chezmoi config. No source command automatically reinitializes or overwrites configurations on existing Macs.

An earlier Desktop Commander/LaunchAgent/Claude pilot is parked in [AgentDesk's archive branch](https://github.com/ArthurZakirov/AgentDesk/tree/chore/park-dotfiles-extras/experiments/parked-dotfiles). Archiving its source did not uninstall the LaunchAgent.

## Testing and validation

The local [test runner](../tests/run.sh) validates shell syntax and exercises installer functions with stubs instead of provisioning the developer's Mac. Python tests use pytest in a Poetry-managed `.venv`. Unit tests live in [`tests/unit/`](../tests/unit/), while [`tests/integration/`](../tests/integration/) covers actual chezmoi rendering and interactive zsh behavior using temporary homes. Shared test helpers live in [`tests/support/`](../tests/support/).

Reviewed snapshots of rendered managed configurations live in [`tests/fixtures/rendered/`](../tests/fixtures/rendered/). The current snapshots cover `.zshrc` and chezmoi TOML for both profiles; more managed files can be added as the repository grows. Tests normalize machine-specific absolute paths and compare each snapshotted file byte-for-byte against its rendered output. Lifecycle hooks are syntax-checked rather than snapshotted.

[macOS GitHub Actions](../.github/workflows/shell.yml) also provisions separate temporary HOME directories for both profiles on ephemeral runners using `chezmoi init --apply`. The runner already includes Homebrew and other macOS tooling; this does not verify Homebrew-from-zero or permission prompts on a completely blank physical Mac. A Linux devcontainer cannot fully reproduce those macOS steps. The CI-only provisioning test refuses to run outside GitHub Actions.

See [setup](setup.md) to provision a machine or [development](development.md) to modify and test this repository.
