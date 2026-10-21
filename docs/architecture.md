# How DevMac is assembled

[← DevMac](../README.md) · [Tool inventory](tool-inventory.md) · [Features by purpose](features/README.md)

DevMac is experienced as a set of developer workflows, but delivered through applications, command-line tools, managed configuration files, and login services. [Browse by outcome](features/README.md) or [audit the tools by kind and installer](tool-inventory.md).

**Chezmoi** is the native entry point. It discovers `<GitHub username>/dotfiles`, clones the repository, generates a machine-local configuration, and applies the declared files. **Git** carries updates between Macs, while **Homebrew** installs dependencies. The supported operating system is macOS.

## Components and order

| File | Description |
|---|---|
| [Official chezmoi installer](https://www.chezmoi.io/install/) | Installs chezmoi and forwards `init --apply USERNAME`; no custom bootstrap downloader. |
| [`home/.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) | Prompts for profile, GitHub username, and optional Bitwarden Keychain account; configures VS Code integration. Credentials stay outside Git. |
| [`home/run_once_before_00-backup-shell.sh.tmpl`](../home/run_once_before_00-backup-shell.sh.tmpl) | Backs up an existing `.zshrc` before the managed version is applied. |
| [`home/run_before_01-snapshot-existing-managed.sh.tmpl`](../home/run_before_01-snapshot-existing-managed.sh.tmpl) | Snapshots existing managed files and symlinks before each apply that has changes; source/destination paths derive from chezmoi, not a checkout location. |
| [`home/run_before_10-install-shell.sh.tmpl`](../home/run_before_10-install-shell.sh.tmpl) | Runs the shell installation process. |
| [`src/shell-setup.sh`](../src/shell-setup.sh) | Reusable shell, editor, and profile installers; selects personal or professional integrations. |
| [`src/homebrew.sh`](../src/homebrew.sh) | Installs Homebrew if missing and configures its shell environment. |
| [`src/apps.sh`](../src/apps.sh) | Checks for installed shared applications and CLIs, installing only missing Homebrew packages. |
| [`Brewfile`](../Brewfile) | Declares Homebrew packages without locking exact package versions. |
| [`home/.chezmoidata.toml`](../home/.chezmoidata.toml) | Stores shared settings including the pinned Oh My Zsh revision. |
| [`home/dot_zshrc.tmpl`](../home/dot_zshrc.tmpl) | Renders shell history, completion, prompt, Git helpers, fzf, and plugins. |
| [`home/dot_gitconfig`](../home/dot_gitconfig) | Renders the shared Git aliases and an optional machine-local override. |
| [`home/run_once_before_15-migrate-git-config.sh`](../home/run_once_before_15-migrate-git-config.sh) | Preserves an existing global Git configuration as the machine-local override. |
| [`home/.chezmoitemplates/personal.zsh`](../home/.chezmoitemplates/personal.zsh) | Adds personal-only integrations such as Bitwarden Secrets Manager CLI and LangSmith. |

The installation hook runs before the managed `~/.zshrc` is applied, so required shell dependencies are available on first shell startup. The backup hook is run-once; the installer hook is idempotent and checks dependencies on subsequent applies.


## CI provisioning scope

The GitHub Actions fresh-home jobs set `DOTFILES_SKIP_OPTIONAL_APPS=1` to skip optional GUI downloads and third-party CLIs. They still exercise chezmoi templates, shell hooks, Oh My Zsh, shared Brewfile packages and (for personal) the Bitwarden Secrets Manager CLI. This avoids flaky upstream app download checksums and very slow GUI installs; mocked tests validate application installation decisions, and an isolated integration test verifies the VS Code `code` symlink behavior.

## Synchronization and safety

Changes committed and pushed on one Mac are available to the other via `chezmoi update`, an **explicit** pull-and-apply operation. Machine-local profile settings stay in that machine's chezmoi config. No source command automatically reinitializes or overwrites configurations on existing Macs.

## Testing and validation

The local [test runner](../tests/run.sh) validates shell syntax and exercises installer functions with stubs instead of provisioning the developer's Mac. Python tests use pytest in a Poetry-managed `.venv`. Unit tests live in [`tests/unit/`](../tests/unit/), while [`tests/integration/`](../tests/integration/) covers actual chezmoi rendering and interactive zsh behavior using temporary homes. Shared test helpers live in [`tests/support/`](../tests/support/).

Reviewed snapshots of rendered managed configurations live in [`tests/fixtures/rendered/`](../tests/fixtures/rendered/). The current snapshots cover `.zshrc` and chezmoi TOML for both profiles; more managed files can be added as the repository grows. Tests normalize machine-specific absolute paths and compare each snapshotted file byte-for-byte against its rendered output. Lifecycle hooks are syntax-checked rather than snapshotted.

[macOS GitHub Actions](../.github/workflows/shell.yml) also provisions separate temporary HOME directories for both profiles on ephemeral runners using `chezmoi init --apply`. The runner already includes Homebrew and other macOS tooling; this does not verify Homebrew-from-zero or permission prompts on a completely blank physical Mac. A Linux devcontainer cannot fully reproduce those macOS steps. The CI-only provisioning test refuses to run outside GitHub Actions.

See [setup](setup.md) to provision a machine or [development](development.md) to modify and test this repository.
