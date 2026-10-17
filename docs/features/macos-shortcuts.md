# macOS native keyboard shortcuts

[← Shared features](README.md) · [Development](../development.md)

macOS does not store all shortcuts in one file. This feature manages the native
shortcut settings that can be safely identified and modified by preference key.
It uses only Python's standard library and the macOS `defaults` utility;
Hammerspoon is not required.

The managed source of truth is
[`home/dot_config/macos-shortcuts/shortcuts.json`](../../home/dot_config/macos-shortcuts/shortcuts.json).
It initially contains the shortcuts exported from the source Mac. Review the
JSON before committing it: shortcut titles may disclose application names or
custom menu labels.

| JSON section | macOS source | Behavior on import |
| --- | --- | --- |
| `system_hotkeys` | `com.apple.symbolichotkeys` / `AppleSymbolicHotKeys` | Merge by numeric hotkey ID, preserving enabled and disabled records |
| `app_shortcuts` | `NSUserKeyEquivalents` in each app domain, including global overrides | Merge by application and exact menu title; register new apps with the System Settings menu |
| `service_shortcuts` | `pbs` / `NSServicesStatus` | Merge by Service ID, preserving unrelated per-Service preferences |
| `accessibility_hotkeys` | `com.apple.universalaccess` / `UserAssignableHotKeys` | Merge by Apple's `sybmolichotkey` identifier, retaining unlisted entries |

Shortcut definitions stored only in applications, default macOS bindings not
materialized in preferences, per-device modifier-key mappings, hardware-specific
function-key behaviors, and third-party key bindings (such as Raycast,
Rectangle, and Hammerspoon) are **not exported or restored by this tool**.
An application may have its own sync/export mechanism. The numeric system
hotkey identifiers are not an Apple-supported cross-version configuration API;
always review a restore when the macOS version or keyboard differs.

## Back up and review

After chezmoi installs `~/.local/bin/macos-shortcuts`, export a Mac's current
configured overrides to a separate, reviewable JSON file:

```sh
macos-shortcuts export ~/Desktop/mac-shortcuts-before.json
macos-shortcuts diff ~/.config/macos-shortcuts/shortcuts.json
```

`export` reads preferences and creates/overwrites **only the named output file**.
`diff` is read-only. Only keys **present in the desired JSON** are managed:
extra local shortcuts are preserved. Removing a key from the file does **not**
delete an existing local shortcut. To change the version-controlled defaults,
edit the source JSON in chezmoi, not a preference plist.

## Apply deliberately on another Mac

First use the repository's [safe update workflow](../setup.md#already-configured-mac-synchronize-safely)
to review and synchronize the managed JSON and CLI. Then:

```sh
macos-shortcuts diff ~/.config/macos-shortcuts/shortcuts.json
macos-shortcuts apply ~/.config/macos-shortcuts/shortcuts.json
# The previous invocation makes no changes; inspect the proposed differences.
macos-shortcuts apply ~/.config/macos-shortcuts/shortcuts.json --yes
```

The `--yes` flag is mandatory for a write. The import updates app menu entries individually. System, Services and
Accessibility preferences require a type-preserving domain import: the tool
merges the declared shortcut entries with a freshly exported copy of **all**
settings in each affected domain and reimports it. Unrelated settings and
shortcut identifiers are retained, but a simultaneous change by another process
while importing a domain could still be lost. Do not run the import while
editing those settings in System Settings. Both CLI operations
work only for the current macOS user.

Relaunch affected apps after applying; system-wide shortcuts may require a
logout/login before the new bindings take effect. The utility does **not**
restart apps, kill `cfprefsd`, or alter live macOS settings as part of
`chezmoi apply`. It deliberately avoids implicit preference writes during
installation. Keep the exported backup to inspect or recover prior shortcut
values. Configuration conflicts and unsupported app shortcuts can still need
manual resolution in System Settings.
