# Raycast navigation

[← Features](README.md) · [Development](../development.md)

Raycast remains **local to each Mac**. Chezmoi installs Raycast and manages
Script Commands, but it never synchronizes Raycast's clipboard history,
credentials, browser activity, databases or account settings. Do not enable
Raycast Cloud Sync as part of this setup.

## Workflows

| Workflow | Mechanism | Setup on each Mac |
| --- | --- | --- |
| Find Git repositories | [Repository Manager](https://www.raycast.com/francesco_mecchi/repository-manager), a Store extension | Install in Raycast, configure projects path and VS Code, assign `Option+R` |
| Open configuration files | [Raycast Script Commands](https://manual.raycast.com/script-commands) managed with chezmoi | Register `~/.config/raycast/scripts` once |
| Other Quicklinks | Keep existing local Raycast Quicklinks | Existing Quicklinks remain unchanged |

The included Script Commands open the following **existing files** in VS Code:

| Raycast command | Path |
| --- | --- |
| Open Codex AGENTS.md | `~/.codex/AGENTS.md` |
| Open Codex config.toml | `~/.codex/config.toml` |
| Open .zshrc | `~/.zshrc` |
| Open AWS config | `~/.aws/config` |
| Open Databricks config | `~/.databrickscfg` |

Missing configuration files produce an error. **The commands never create
blank credentials/config files.** Machine-specific files and their contents are
not checked into Git.

## First-time initialization

On a normal interactive Mac, `chezmoi apply` creates the scripts and opens
Repository Manager's official Store listing **once per machine**. Confirm
installation in Raycast, then:

1. In Raycast, open **Settings → Extensions → Script Commands**, add
   `~/.config/raycast/scripts` as a Script Directory.
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
marker is not an installation-health indicator. With
`DOTFILES_SKIP_OPTIONAL_APPS=1`, onboarding is deferred until the next normal
`chezmoi apply`. Raycast must already be installed; installation is managed by
[`src/apps.sh`](../../src/apps.sh).

## Managed sources and data boundaries

| Purpose | Source |
| --- | --- |
| Five Script Commands | [`home/dot_config/raycast/scripts/`](../../home/dot_config/raycast/scripts/) |
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
