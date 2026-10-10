# How it works

[← README](../README.md)

**Chezmoi** is the native entry point. It discovers `<GitHub username>/dotfiles`, clones the repository, generates a machine-local configuration, and applies the declared files. **Git** carries updates between Macs, while **Homebrew** installs dependencies. The supported operating system is macOS.

## Components and order

1. The [official chezmoi installer](https://www.chezmoi.io/install/) installs chezmoi and forwards `init --apply USERNAME`. There is no custom remote bootstrap downloader.
2. The [chezmoi configuration template](../home/.chezmoi.toml.tmpl) prompts for the personal or professional profile, GitHub username, and optionally the Bitwarden Keychain account. Credentials stay outside Git. It configures VS Code for chezmoi editing and diffs.
3. The [once-before backup hook](../home/run_once_before_00-backup-shell.sh.tmpl) backs up a pre-existing zshrc before chezmoi applies the rendered version.
4. The [shell installation hook](../home/run_before_10-install-shell.sh.tmpl) invokes the reusable [shell setup module](../src/shell-setup.sh). The shared [Homebrew module](../src/homebrew.sh) installs Homebrew if needed, then configures its environment.
5. The [Brewfile](../Brewfile) lists Homebrew packages. Package versions follow Homebrew; this is a reproducible configuration, not an exact version-locked image. The module also installs VS Code, Oh My Zsh, and profile-specific tools.
6. [Shared chezmoi data](../home/.chezmoidata.toml) contains the pinned Oh My Zsh revision. If aligning that revision would overwrite tracked local changes, installation stops.
7. The [zsh template](../home/dot_zshrc.tmpl) renders history, completion, prompt, Git helpers, fzf, and plugins. Only the personal profile includes [personal integrations](../home/.chezmoitemplates/personal.zsh), including Bitwarden Secrets Manager CLI and LangSmith.

The installation hook runs before the managed `~/.zshrc` is applied, so required shell dependencies are available on first shell startup. The backup hook is run-once; the installer hook is idempotent and checks dependencies on subsequent applies.

## Synchronization and safety

Changes committed and pushed on one Mac are available to the other via `chezmoi update`, an **explicit** pull-and-apply operation. Machine-local profile settings stay in that machine's chezmoi config. No source command automatically reinitializes or overwrites configurations on existing Macs.

An earlier Desktop Commander/LaunchAgent/Claude pilot is parked in [AgentDesk's archive branch](https://github.com/ArthurZakirov/AgentDesk/tree/chore/park-dotfiles-extras/experiments/parked-dotfiles). Archiving its source did not uninstall the LaunchAgent.

See [setup](setup.md) to provision a machine or [development](development.md) to modify and test this repository.
