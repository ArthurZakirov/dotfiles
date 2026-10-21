# Raycast navigation

[← Features](README.md) · [Review and navigation](../workflows/review-and-navigation.md) · [Development](../development.md)

Raycast provides optional navigation to Git repositories and frequently used
configuration files directly from the keyboard. Chezmoi installs the app and
manages file-opening Script Commands; other DevMac workflows do not depend on
Raycast onboarding. Raycast stays **local to each Mac**: this feature does not
synchronize clipboard history, credentials, browser activity, databases, or
account settings. Raycast Cloud Sync is not needed.

## Workflows

| Workflow | Mechanism | Setup on each Mac |
| --- | --- | --- |
| Launch installed applications | Raycast's built-in app search | Raycast app installed by DevMac; no extension required |
| Find Git repositories | [Repository Manager](https://www.raycast.com/francesco_mecchi/repository-manager), a Store extension | Install in Raycast, configure projects path and VS Code, assign `Option+R` |
| Open specific files and folders | [Raycast Script Commands](https://manual.raycast.com/script-commands) managed with chezmoi | Register `~/.config/raycast/scripts` once |

**Repository Manager lists Git repositories dynamically; it does not provide
shortcuts to arbitrary files or directories.** Raycast discovers the separately
managed Script Commands from `~/.config/raycast/scripts`. Register that folder
once per Mac; subsequent `chezmoi apply` runs update its contents without
regenerating or importing Quicklinks JSON.

Each command file supplies only its searchable Raycast metadata and a target
argument. One shared launcher handles file/folder checks and opens the target
in VS Code. For example, `.zshrc` delegates to:

```bash
exec "$HOME/.config/raycast/lib/open-target.sh" file "$HOME/.zshrc"
```

The launcher lives under `~/.config/raycast/lib`, **outside** the registered
Script Commands directory, so Raycast does not index it as another command.
It also resolves the `chezmoi dotfiles` repository dynamically.

## Managed file and folder shortcuts

The following eight commands replace the entries in the existing local
`~/.config/raycast/quicklinks.json`. Their Raycast titles match the original
Quicklink names, and they open the same destinations in VS Code:

| Raycast command | Destination | Type |
| --- | --- | --- |
| `quicklinks.json` | `~/.config/raycast/quicklinks.json` | File |
| `.local/bin scripts` | `~/.local/bin` | Folder |
| `.zshrc` | `~/.zshrc` | File |
| `repos/personal` | `~/Repos/personal` | Folder |
| `repos` | `~/Repos` | Folder |
| `config.toml` | `~/.codex/config.toml` | File |
| `.codex` | `~/.codex` | Folder |
| `chezmoi dotfiles` | Git root containing `chezmoi source-path` | Folder |

The `chezmoi dotfiles` command resolves the repository root dynamically, so it
does not depend on a machine-specific checkout or symlink. The repository
shortcuts use DevMac's `~/Repos` directory convention.

Three additional commands open the config files discussed when designing this
feature:

| Raycast command | Destination |
| --- | --- |
| `Open Codex AGENTS.md` | `~/.codex/AGENTS.md` |
| `Open AWS config` | `~/.aws/config` |
| `Open Databricks config` | `~/.databrickscfg` |

Missing targets produce an error rather than creating blank files or folders.
Machine-specific configuration and credentials remain outside Git.

## First-time initialization

On a normal interactive Mac, `chezmoi apply` creates the scripts and opens
Repository Manager's official Store listing **once per machine**. This is an
onboarding prompt, not unattended extension installation. Confirm installation
in Raycast, then:

1. In Raycast, open **Settings → Script Commands → Add Script Directory** and
   select `~/.config/raycast/scripts`.
2. Open Repository Manager's preferences, set your Git projects path and VS Code
   as editor, and choose **Open in Editor** as its primary action.
3. Assign `Option+R` to Repository Manager's repository-list command in Raycast.

After verifying the new file commands, remove only their superseded file
Quicklinks in Raycast if you want to avoid duplicate search results. The
migration deliberately leaves existing Quicklinks intact until then.

Raycast does **not** document a CLI to query whether Store extensions are
installed, silently install them, register script directories, or configure
extension hotkeys. The hook therefore records that the **Store link was opened**,
not that the extension was installed. On an already-configured Mac it may open
the listing unnecessarily once; later `chezmoi apply` runs do not repeat it.

The marker is local at `~/.cache/chezmoi/raycast-repository-manager-store-opened`.
If installation was skipped or interrupted, use the Store link above; the
marker is not an installation-health indicator. Raycast must already be installed; installation is managed by
[`src/apps.sh`](../../src/apps.sh).

## Managed sources and data boundaries

| Purpose | Source |
| --- | --- |
| Eleven Raycast command wrappers | [`home/dot_config/raycast/scripts/`](../../home/dot_config/raycast/scripts/) |
| Shared target-opening launcher | [`home/dot_config/raycast/lib/executable_open-target.sh`](../../home/dot_config/raycast/lib/executable_open-target.sh) |
| One-time Store onboarding | [`home/run_after_60-raycast-onboarding.sh`](../../home/run_after_60-raycast-onboarding.sh) |
| Raycast app provisioning | [`src/apps.sh`](../../src/apps.sh) |
| Tests | [`tests/integration/test_raycast.py`](../../tests/integration/test_raycast.py) |

Chezmoi does **not** import or edit the existing
`~/.config/raycast/quicklinks.json`, local Raycast data, or `.rayconfig`
exports. Backups can include unrelated private/work data and must not be
committed to a shared repository.

**Git worktrees:** Repository Manager currently recognizes a `.git`
*directory*, while linked worktrees typically have a `.git` *file*. These
worktrees will not appear in its list without an upstream fix. This feature
does not fork or patch that Store extension; its automatic Store updates remain
intact.
