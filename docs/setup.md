# Set up or synchronize a Mac

[← README](../README.md)

## Which setup case applies?

**Step 1 — Run this read-only diagnosis in Terminal (copy/paste):**

```sh
if ! command -v chezmoi >/dev/null 2>&1; then
  echo 'NOT INSTALLED'
elif ! source_dir="$(chezmoi source-path 2>/dev/null)" || [[ ! -d "$source_dir" ]]; then
  echo 'NOT INITIALIZED'
elif [[ -z "$(chezmoi managed 2>/dev/null)" ]]; then
  echo 'NOT INITIALIZED'
else
  echo 'MANAGED'
fi
```

**Step 2 — Follow the section matching the printed status:**

| Status | Section |
|---|---|
| `NOT INSTALLED` (new/unconfigured Mac) | [New Mac: one native chezmoi command](#new-mac-one-native-chezmoi-command) |
| `NOT INSTALLED` (previously configured Mac) | [Inspect your installation](#inspect-your-installation) |
| `NOT INITIALIZED` | [Inspect your installation](#inspect-your-installation) |
| `MANAGED` | [Already configured Mac: synchronize safely](#already-configured-mac-synchronize-safely) |

**Do not run `init --apply` on an existing Mac until you have inspected and preserved its configuration.**

## New Mac: one native chezmoi command

1. If this Mac already has a chezmoi configuration, **stop** and follow [Inspect your installation](#inspect-your-installation) first. To preserve an existing config before initializing, run:

   ```sh
   config="$HOME/.config/chezmoi/chezmoi.toml"
   if [[ -f "$config" ]]; then
     cp -p "$config" "${config}.backup.$(date +%Y%m%d-%H%M%S)"
   fi
   ```
2. Run the [official chezmoi installer](https://www.chezmoi.io/install/). Select **personal** or **professional** when prompted. Approve any expected macOS administrator or Command Line Tools prompts:

   ```sh
   export GITHUB_USERNAME="ArthurZakirov"
   sh -c "$(curl -fsLS https://get.chezmoi.io)" -- init --apply "$GITHUB_USERNAME"
   ```
3. Open a new Terminal, then verify:

   ```sh
   chezmoi source-path
   chezmoi managed
   chezmoi execute-template '{{ .profile }}'
   ```

4. If you had a previous `~/.zshrc`, check the backup in `~/Library/Application Support/dotfiles/backups/` before deleting anything.

For the underlying provisioning sequence, see [Architecture](architecture.md).

## Already configured Mac: synchronize safely

1. **Do not rerun the new-Mac installer.** Check the active source and your local Git changes:

   ```sh
   chezmoi source-path
   git -C "$(chezmoi source-path)" status --short --branch
   ```

2. Fetch the latest source changes without applying them. **Only if the working tree is clean:**

   ```sh
   git -C "$(chezmoi source-path)" pull --ff-only
   ```

3. If [`.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) changed, save a timestamped copy of the current local config (if it exists), then regenerate it **without applying**:

   ```sh
   config="$HOME/.config/chezmoi/chezmoi.toml"
   if [[ -f "$config" ]]; then
     cp -p "$config" "${config}.backup.$(date +%Y%m%d-%H%M%S)"
   fi
   chezmoi init
   ```

   Check the generated file against the backup before continuing.
4. Review the proposed changes **before running any install hooks**:

   ```sh
   chezmoi --no-pager --use-builtin-diff diff --exclude scripts
   chezmoi --dry-run --verbose apply
   ```

   Both commands work without VS Code and do not modify the destination.
   For the visual comparison, `chezmoi diff` opens VS Code diff tabs. Confirm
   that the tabs actually appear and that their contents are readable; a
   successful exit code alone cannot confirm the editor displayed them.
   Compare paths against `chezmoi source-path` before using a secondary checkout.
5. **Only after reviewing the preview**, apply with interactive confirmation:

   ```sh
   chezmoi apply --interactive
   ```

   When a managed target differs, an early `run_before` hook first snapshots
   existing managed files and symlinks to the machine-local
   `~/Library/Application Support/dotfiles/backups/apply.*` directory.
   These private backups are deliberately retained for recovery. They cannot
   undo arbitrary external side effects (package upgrades or service restarts).
   To avoid disconnecting an active Remote Desktop Commander session, changes
   to its running LaunchAgent are deferred until the operator explicitly runs
   the relevant apply with `DOTFILES_ALLOW_SERVICE_INTERRUPTION=1`.

   `apply` invokes hooks with side effects (including missing package
   installation and LaunchAgent reconciliation), even if managed files are
   unchanged. Review active services, existing file changes, and backups
   before proceeding. For a file-only preview on an existing Mac, use
   `chezmoi diff` or `chezmoi apply --dry-run --exclude scripts` instead of
   adding package-selection flags. Keep `--force` for explicitly accepted
   overwrites only.

## Inspect your installation

```sh
chezmoi source-path
chezmoi managed
chezmoi execute-template '{{ .profile }}'
```

If the source path is missing or unexpected, **stop** before applying anything. To change the personal Bitwarden Keychain account, run `chezmoi init --prompt` and review the generated configuration. For implementation details, see [Architecture](architecture.md).
