# Develop the repository

[← README](../README.md) · [Architecture](architecture.md)

## Edit and propagate changes

Use chezmoi to edit the managed source and preview the resulting configuration:

```sh
chezmoi edit ~/.zshrc
chezmoi diff
chezmoi apply
chezmoi git -- add .
chezmoi git -- commit -m "Update shared shell configuration"
chezmoi git -- push
```

The [chezmoi config template](../home/.chezmoi.toml.tmpl) configures VS Code as the editor and diff tool. Changes become available on another Mac after `chezmoi update`.

Keep scripts in `scripts/` as `run_*` entry points, and reusable logic in `src/` instead of duplicating functions. Update the [Brewfile](../Brewfile) for shell packages, [chezmoi data](../home/.chezmoidata.toml) for shared constants, and the [zsh template](../home/dot_zshrc.tmpl) for shell behavior. Account-specific additions belong in [personal.zsh](../home/.chezmoitemplates/personal.zsh); `~/.zshrc.local` is for untracked local overrides.

## Tests

Run from the repository root:

```sh
./tests/run.sh
```

The runner validates shell syntax and bootstrap input handling, renders personal and professional profiles, checks that personal integrations do not leak to professional profiles, and exercises interactive shell initialization without accessing secrets. The same runner is used in [macOS CI](../.github/workflows/shell.yml). A full clean-machine bootstrap still depends on macOS permissions and network access.
