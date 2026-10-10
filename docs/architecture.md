# How it works

[← README](../README.md)

**Chezmoi** is the native entry point. It discovers `<GitHub username>/dotfiles`, clones the repository, generates a machine-local configuration, and applies the declared files. **Git** carries updates between Macs, while **Homebrew** installs dependencies. The supported operating system is macOS.

## Components and order

1. The [official chezmoi installer](https://www.chezmoi.io/install/) installs chezmoi and forwards `init --apply USERNAME`. There is no custom remote bootstrap downloader.
2. The [`.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) prompts for the personal or professional profile, GitHub username, and optionally the Bitwarden Keychain account. Credentials stay outside Git. It configures VS Code for chezmoi editing and diffs.
3. The [`run_once_before_00-backup-shell.sh.tmpl`](../home/run_once_before_00-backup-shell.sh.tmpl) backs up a pre-existing zshrc before chezmoi applies the rendered version.
4. The [`run_before_10-install-shell.sh.tmpl`](../home/run_before_10-install-shell.sh.tmpl) invokes the reusable [`shell-setup.sh`](../src/shell-setup.sh). The shared [`homebrew.sh`](../src/homebrew.sh) installs Homebrew if needed, then configures its environment.
5. The [Brewfile](../Brewfile) lists Homebrew packages. Package versions follow Homebrew; this is a reproducible configuration, not an exact version-locked image. The editor factory `install_editors` delegates to the dedicated `install_visual_studio_code` installer; `install_profile` selects `install_personal_profile` or `install_professional_profile`. The personal profile calls `install_bitwarden_secrets_manager` while the professional profile currently needs no extra installations. Oh My Zsh is shared by both profiles.
6. [`.chezmoidata.toml`](../home/.chezmoidata.toml) contains the pinned Oh My Zsh revision. If aligning that revision would overwrite tracked local changes, installation stops.
7. The [`dot_zshrc.tmpl`](../home/dot_zshrc.tmpl) renders history, completion, prompt, Git helpers, fzf, and plugins. Only the personal profile includes [`personal.zsh`](../home/.chezmoitemplates/personal.zsh), including Bitwarden Secrets Manager CLI and LangSmith.

The installation hook runs before the managed `~/.zshrc` is applied, so required shell dependencies are available on first shell startup. The backup hook is run-once; the installer hook is idempotent and checks dependencies on subsequent applies.

## Synchronization and safety

Changes committed and pushed on one Mac are available to the other via `chezmoi update`, an **explicit** pull-and-apply operation. Machine-local profile settings stay in that machine's chezmoi config. No source command automatically reinitializes or overwrites configurations on existing Macs.

An earlier Desktop Commander/LaunchAgent/Claude pilot is parked in [AgentDesk's archive branch](https://github.com/ArthurZakirov/AgentDesk/tree/chore/park-dotfiles-extras/experiments/parked-dotfiles). Archiving its source did not uninstall the LaunchAgent.

## Testing and validation

The local [test runner](../tests/run.sh) validates shell syntax and exercises installer functions with stubs instead of provisioning the developer's Mac. Python tests use pytest in a Poetry-managed `.venv`. Unit tests live in [`tests/unit/`](../tests/unit/), while [`tests/integration/`](../tests/integration/) covers actual chezmoi rendering and interactive zsh behavior using temporary homes. Shared test helpers live in [`tests/support/`](../tests/support/).

The complete rendered `.zshrc` and chezmoi TOML configurations for both profiles are stored in [`tests/fixtures/rendered/`](../tests/fixtures/rendered/) as reviewed snapshots. Tests normalize absolute machine paths and compare each generated configuration byte-for-byte with its snapshot. Lifecycle hooks are syntax-checked rather than snapshotted.

[macOS GitHub Actions](../.github/workflows/shell.yml) also provisions separate temporary HOME directories for both profiles on ephemeral runners using `chezmoi init --apply`. The runner already includes Homebrew and other macOS tooling; this does not verify Homebrew-from-zero or permission prompts on a completely blank physical Mac. A Linux devcontainer cannot fully reproduce those macOS steps. The CI-only provisioning test refuses to run outside GitHub Actions.

See [setup](setup.md) to provision a machine or [development](development.md) to modify and test this repository.
