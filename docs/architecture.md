# How it works

[← README](../README.md)

**Git** versions the shared configuration, **chezmoi** renders and applies it per machine, and **Homebrew** installs dependencies. The current scope is macOS shell and editor setup, with personal and professional profiles.

## Components

1. The [bootstrap entry point](../scripts/run_bootstrap.sh) orchestrates first-time setup, using the [bootstrap module](../src/bootstrap.sh) and shared [Homebrew module](../src/homebrew.sh).
2. The [Brewfile](../Brewfile) declares required packages. Package versions come from Homebrew; this is not a version-locked image.
3. The [chezmoi configuration template](../home/.chezmoi.toml.tmpl) selects the machine's profile and GitHub username, and on personal Macs the Bitwarden Keychain account. Credentials remain outside Git. It also configures VS Code for `chezmoi edit` and `chezmoi diff`.
4. [Shared template data](../home/.chezmoidata.toml) includes the desired Oh My Zsh revision.
5. The [installation hook](../home/run_before_10-install-shell.sh.tmpl) calls the [shell setup module](../src/shell-setup.sh).
6. The [shared zsh template](../home/dot_zshrc.tmpl) defines history, completion, prompt, Git helpers, fzf and plugins. Only the personal profile includes [personal integrations](../home/.chezmoitemplates/personal.zsh), including Bitwarden Secrets Manager CLI and LangSmith.

Setup stops rather than overwriting tracked local Oh My Zsh changes when revision alignment is necessary.

## Synchronization model

Configuration changes committed and pushed from one Mac become available to others via `chezmoi update`. This is an **explicit** pull-and-apply operation, not background synchronization. The selected profile and its machine-local settings stay local; shared templates live in Git.

An earlier Desktop Commander/LaunchAgent/Claude pilot is parked in [AgentDesk's archive branch](https://github.com/ArthurZakirov/AgentDesk/tree/chore/park-dotfiles-extras/experiments/parked-dotfiles). Archiving its source did not uninstall its LaunchAgent.

For first-time installation, see [setup](setup.md). For changing scripts or templates, see [development](development.md).
