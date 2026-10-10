# Set up or synchronize a Mac

[← README](../README.md)

## Which setup case applies?

Run these read-only checks in Terminal:

```sh
command -v chezmoi
chezmoi source-path
chezmoi managed
```

- **`command -v chezmoi` prints nothing:** Chezmoi is not available on your PATH. For a new Mac, follow [New Mac: one native chezmoi command](#new-mac-one-native-chezmoi-command).
- **Chezmoi is installed, but `source-path` is missing or `managed` lists no files:** Chezmoi may not yet be initialized. See [New Mac: one native chezmoi command](#new-mac-one-native-chezmoi-command), but do not use `init --apply` on an existing configured Mac without inspecting and backing up its settings first.
- **`source-path` exists and `managed` lists files such as `.zshrc`:** Follow [Already configured Mac: synchronize safely](#already-configured-mac-synchronize-safely).
- **Unsure which repository or profile is active?** Follow [Inspect your installation](#inspect-your-installation) before making changes.

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
