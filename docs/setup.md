# Set up or synchronize a Mac

[← README](../README.md)

## Bootstrap

On a personal Mac, run:

```sh
export GITHUB_USERNAME="ArthurZakirov"
/bin/bash -c "$(curl -fsSL "https://raw.githubusercontent.com/${GITHUB_USERNAME}/dotfiles/HEAD/scripts/run_bootstrap.sh")" -- personal
```

For a professional Mac, replace `personal` with `professional`. The GitHub username identifies the `<username>/dotfiles` repo. The script uses the default branch (remote HEAD) unless `DOTFILES_BRANCH` is set.

**Until this feature branch is merged into the default branch**, run from an existing checkout:

```sh
/bin/bash scripts/run_bootstrap.sh personal
```

macOS may ask for an administrator password or Command Line Tools approval. The installer backs up existing zsh/configuration files to a timestamped directory and prints its location. Start a new terminal after setup. Personal Macs may require separate one-time Bitwarden authentication; the shell works before that Keychain entry exists.

The installer covers the shell and editor, not the whole workstation. Optional Raycast shortcuts and `sync-systemsmith` require external tooling not installed here.

## Synchronize

Synchronization is **manual**, through Git and chezmoi. After committing and pushing changes from one Mac, run on another:

```sh
chezmoi update
```

This pulls and applies changes. `chezmoi apply` checks dependencies but does not upgrade installed packages; upgrade Homebrew packages deliberately.

## Inspect and configure

```sh
chezmoi source-path
chezmoi managed
chezmoi execute-template '{{ .profile }}'
```

To change the personal Bitwarden Keychain account, use `chezmoi init --prompt` and answer the prompts. Use untracked `~/.zshrc.local` for optional machine-specific additions. For the component model see [architecture](architecture.md); for editing and testing see [development](development.md).
