# Hammerspoon shortcuts

[← Features](README.md) · [Development](../development.md)

Chezmoi manages **the same complete Hammerspoon configuration on personal and
professional Macs** at `~/.hammerspoon/`. No Hammerspoon functionality is
profile-specific.

**Shortcut notation:** `Hyper` = `Ctrl+Alt+Cmd`. Display numbers follow
left-to-right screen order (then top-to-bottom).

## Window and display controls

| Shortcut | Action |
| --- | --- |
| `Ctrl+Alt+←` / `Ctrl+Alt+→` | Move focused window to left / right half |
| `Ctrl+Alt+Return` | Maximize focused window |
| `Hyper+J/K/L/;` | Send focused window to display 1/2/3/4 |
| `Hyper+1/2/3/4` | Alternate send-to-display shortcuts |
| `Hyper+U/I/O/P` | Focus display 1/2/3/4 |
| `Hyper+N` | Focus next display |
| `Hyper+H` | Identify numbered displays |
| `Hyper+/` | Searchable window picker |

## Spaces and Mission Control

| Shortcut | Action |
| --- | --- |
| `Hyper+,` / `Hyper+.` | Switch to previous / next Space |
| `Hyper+M` / `Hyper+-` | Move focused window to previous / next Space |
| `Hyper++` | Create a Space |
| `Hyper+Delete` | Enter desktop-deletion mode (select 1–9; Esc/Return to exit) |
| `Hyper+Space` | Toggle Mission Control |
| `Hyper+Z` | Toggle App Exposé for focused app |

## Application shortcuts

| Context | Shortcut | Action |
| --- | --- | --- |
| Chrome | `Hyper+B` / `Hyper+T` / `Hyper+G` | Search bookmarks / tabs / history |
| ChatGPT (German keyboard) | `Cmd+Shift+7` | Open native Keyboard Shortcuts menu |
| Claude | `Ctrl+Alt+R` | Close / restore right pane |
| Claude | `Ctrl+Alt+M` | Expand / collapse pane |
| Claude | `Ctrl+Alt+J` / `Ctrl+Alt+K` | Fold all sidebar groups / toggle one group |
| Claude | `Ctrl+Alt+L` / `Ctrl+Alt+O` | Sidebar view menu / group-sort-filter chooser |
| Claude | `Ctrl+Alt+P` | Session actions menu |
| Claude | `Ctrl+Alt+D` or double-tap right `Cmd` | Toggle dictation |
| Claude | `Ctrl+Alt+H` | Interactive action palette |
| All apps | `Hyper+Ä` | SteelSeries audio and microphone check |
| All apps | `Hyper+R` | Reload Hammerspoon configuration |

Claude shortcuts activate only when Claude is frontmost. The ChatGPT shortcut
activates only when ChatGPT is frontmost and the input source is German/QWERTZ.
The audio check is available on **both** profiles; its expected device names
are defined in the shared source, so a Mac without those devices can show
device warnings without preventing the rest of Hammerspoon from working.

## Managed components

| Purpose | Source |
| --- | --- |
| Entrypoint and bindings | [`home/dot_hammerspoon/init.lua`](../../home/dot_hammerspoon/init.lua), [`modules/`](../../home/dot_hammerspoon/modules/) |
| Audio check | [`modules/audio_check.lua`](../../home/dot_hammerspoon/modules/audio_check.lua) |
| Microphone meter | [Swift source and lazy build wrapper](../../home/dot_hammerspoon/bin/) |
| Application installation | [`dependencies/brew/common/gui.Brewfile`](../../dependencies/brew/common/gui.Brewfile) via [`src/apps.sh`](../../src/apps.sh) |
| Existing-config migration | [`run_once_before_05-migrate-hammerspoon.sh`](../../home/run_once_before_05-migrate-hammerspoon.sh) |
| Start, reload and health check | [`run_after_30-ensure-hammerspoon.sh`](../../home/run_after_30-ensure-hammerspoon.sh), [`hammerspoon-activate`](../../home/dot_local/bin/executable_hammerspoon-activate), [`hammerspoon-verify`](../../home/dot_local/bin/executable_hammerspoon-verify) |
| Swift compiler setup | [`hammerspoon-ensure-swiftc`](../../home/dot_local/bin/executable_hammerspoon-ensure-swiftc) and [feature-runtime Brewfile](../../dependencies/brew/common/features/hammerspoon-swift.Brewfile) |

If `swiftc` is missing, the first-run hook provisions a Swift toolchain using
Homebrew. The microphone wrapper also provisions it on demand, including if a
previous setup was interrupted. macOS privacy approvals remain user-controlled.
The audio meter builds locally from Swift source when first invoked and caches
the executable in `~/.cache/hammerspoon/`. Compiled binaries and diagnostic
logs are not version-controlled.

## Installation and verification

On an interactive macOS session, `chezmoi apply` installs the managed files,
starts Hammerspoon if stopped **or reloads it if already running**, and then
checks that the new configuration finished loading with a fresh activation
nonce, the expected baseline hotkey count, and required macOS permissions.
Failure to activate or verify produces a nonzero apply status rather than a
misleading success. If there is no GUI login session or the app is not installed,
activation is skipped; hotkeys cannot work until Hammerspoon is available.
Conditional Claude and ChatGPT shortcuts only activate in their respective apps.
The verification cannot physically press keys or guarantee that macOS or
other applications will not intercept a shortcut.

Run the verifier separately when needed:

```sh
hammerspoon-verify
```

It checks Hammerspoon IPC responsiveness, Accessibility status, autolaunch,
whether the audio module loaded, and whether hotkeys are registered. If the
`hs` CLI is absent from `PATH`, it uses the executable bundled in Hammerspoon.app.
It does not establish that a shortcut actually moved a window or detected speech.

**User approvals still required:** macOS Accessibility and microphone
permissions cannot be granted programmatically. The first microphone access
may prompt when the audio test is invoked. Actual keyboard, window, and
microphone behavior needs a controlled GUI/device check; automated structural
tests are not a substitute for that verification.

## Migrating an existing Mac

Follow the [existing-Mac synchronization workflow](../setup.md#already-configured-mac-synchronize-safely).
The one-time hook backs up the existing `~/.hammerspoon` configuration and
`~/.hammerspoon-local` (if present) under
`~/Library/Application Support/dotfiles/backups/`. It supports ordinary files,
subdirectories and symlinks with **arbitrary targets**, including a symlinked
`~/.hammerspoon` directory. Existing symlink targets are never modified;
replaced symlinks' contents are also copied into the backup. Chezmoi then
manages `init.lua`, `modules/` and `bin/`, retaining unrelated files such as
`Spoons/` and custom modules with non-conflicting names. An existing script
whose path collides with a managed file is preserved in the backup rather than
kept active. A broken top-level `~/.hammerspoon` symlink stops migration instead
of being overwritten.

**Do not reinstall a previous symlink-based configuration:**
it would replace the managed files with external links. Make future
configuration changes in this dotfiles repository.
