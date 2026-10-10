# Set up or synchronize a Mac

[← README](../README.md)

## Which setup case applies?

| Check (read-only) | Result | Action |
|---|---|---|
| `command -v chezmoi` | No output; new/unconfigured Mac | [New Mac setup](#new-mac-one-native-chezmoi-command) |
| `command -v chezmoi` | No output; existing Mac with custom configuration | [New Mac setup](#new-mac-one-native-chezmoi-command) — review backup precautions before installing |
| `chezmoi source-path` and `chezmoi managed` | Source missing or no managed files | [Inspect your installation](#inspect-your-installation) first; preserve existing configuration before any `init --apply` |
| `chezmoi source-path` and `chezmoi managed` | Source exists and managed files are listed | [Synchronize an already configured Mac](#already-configured-mac-synchronize-safely) |
| `chezmoi execute-template '{{ .profile }}'` | Profile or repository unclear | [Inspect your installation](#inspect-your-installation) |

## New Mac: one native chezmoi command

On a **new** Mac, choose your GitHub account and run the [official chezmoi installer](https://www.chezmoi.io/install/):

```sh
export GITHUB_USERNAME="ArthurZakirov"
sh -c "$(curl -fsLS https://get.chezmoi.io)" -- init --apply "$GITHUB_USERNAME"
```

Chezmoi natively discovers `$GITHUB_USERNAME/dotfiles` on GitHub, clones the default branch, prompts you to select the **personal** or **professional** profile, and applies the configuration. Its installation hook provisions Homebrew if missing, the packages in [Brewfile](../Brewfile), VS Code, and Oh My Zsh. Only the personal profile also installs Bitwarden Secrets Manager CLI and enables LangSmith.

macOS may request administrator authorization or installation of Apple Command Line Tools. On personal Macs, Bitwarden authentication is a separate one-time step; the shell can start before the Keychain account is configured. Open a new Terminal after installation.

If an existing `~/.zshrc` is present, a run-once hook saves a timestamped copy in `~/Library/Application Support/dotfiles/backups/` before it is replaced. **An existing chezmoi configuration is generated during `init`, before that hook runs**; copy `~/.config/chezmoi/chezmoi.toml` separately if you need to preserve it. Chezmoi normally prompts before overwriting modified managed files; the installation instructions do not use `--force`.

The installer covers the shell and editor, not the entire workstation. Raycast shortcuts and `sync-systemsmith` are optional integrations; their other dependencies are not installed here.

## Already configured Mac: synchronize safely

**Do not rerun the new-Mac installer on an already configured Mac.** Work from its current chezmoi repository, review changes, then apply deliberately:

```sh
chezmoi diff
chezmoi apply
```

To fetch and apply changes **after you are ready**, use `chezmoi update`. Changes are propagated through Git and chezmoi explicitly, not synchronized automatically. Homebrew packages are checked but not automatically upgraded.

For changes to the chezmoi configuration template (such as the VS Code editor/diff settings), `chezmoi init` can regenerate the local `~/.config/chezmoi/chezmoi.toml`; inspect and back up the current config first. It can prompt for profile and other machine-local options.

## Inspect your installation

```sh
chezmoi source-path
chezmoi managed
chezmoi execute-template '{{ .profile }}'
```

To change the personal Bitwarden Keychain account, use `chezmoi init --prompt`. Place optional machine-local additions in untracked `~/.zshrc.local`. See [architecture](architecture.md) and [development](development.md).
