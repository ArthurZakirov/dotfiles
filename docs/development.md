# Develop the repository

[← README](../README.md) · [Architecture](architecture.md)

## Change and share configuration

Chezmoi edits the managed source and can show the rendered difference:

```sh
chezmoi edit ~/.zshrc
chezmoi diff
chezmoi apply
chezmoi git -- add .
chezmoi git -- commit -m "Update shared shell configuration"
chezmoi git -- push
```

The [chezmoi config template](../home/.chezmoi.toml.tmpl) configures VS Code for editing and diff views. Another Mac can fetch and apply committed changes with `chezmoi update`.

Reusable implementation belongs in [`src/`](../src/shell-setup.sh); lifecycle entry points belong in the [chezmoi hooks](../home/run_before_10-install-shell.sh.tmpl). Keep functions reusable rather than copying installer logic. Update the [Brewfile](../Brewfile) for required Homebrew packages, [chezmoi data](../home/.chezmoidata.toml) for shared settings, and the [zsh template](../home/dot_zshrc.tmpl) for shell behavior. Personal-only additions belong in [personal.zsh](../home/.chezmoitemplates/personal.zsh); local-only overrides can be placed in untracked `~/.zshrc.local`.

## Tests

The local test runner is **read-only with respect to your Mac's setup**: it renders templates, validates syntax, and stubs installation functions rather than running the installers.

```sh
./tests/run.sh
```

The tests validate the provisioning sequence, render both profiles, ensure personal integrations are absent from the professional profile, and check interactive shell initialization without reading secrets. [GitHub Actions](../.github/workflows/shell.yml) additionally runs isolated fresh-home provisioning integration tests for both personal and professional profiles on ephemeral macOS runners via [`tests/run_fresh_home.sh`](../tests/run_fresh_home.sh). That integration test refuses to run outside GitHub Actions. The hosted runner already has Homebrew; full bare-metal installation and permissions must still be verified separately if needed.

Review your Git diff and CI checks before merging the feature branch. Do not run a destructive first-time provisioning test on an existing Mac.
