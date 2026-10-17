# macOS keyboard shortcuts

[← Shared features](README.md) · [Development](../development.md)

Manage native macOS keyboard shortcut overrides across Macs using chezmoi.
The `macos-shortcuts` CLI exports shortcuts to JSON, compares them with the
desired configuration, and applies reviewed changes.

The version-controlled configuration is
[`home/dot_config/macos-shortcuts/shortcuts.json`](../../home/dot_config/macos-shortcuts/shortcuts.json),
initially exported from the source Mac. Review shortcut titles before committing:
custom menu labels may contain personal information.

## Managed shortcuts

| JSON section | macOS preference | Synchronization |
| --- | --- | --- |
| `system_hotkeys` | `com.apple.symbolichotkeys` / `AppleSymbolicHotKeys` | Merge enabled states and key bindings by numeric hotkey ID |
| `app_shortcuts` | `NSUserKeyEquivalents` in each app domain, including global overrides | Merge by application and menu title, registering applications with System Settings |
| `service_shortcuts` | `pbs` / `NSServicesStatus` | Merge shortcuts by Service ID |
| `accessibility_hotkeys` | `com.apple.universalaccess` / `UserAssignableHotKeys` | Merge by Apple's `sybmolichotkey` identifier |

The import preserves additional local shortcuts and unrelated preferences.
For portability, review numeric system-hotkey IDs when transferring settings
between macOS versions or keyboard layouts.

## Export and compare

After chezmoi installs `~/.local/bin/macos-shortcuts`, create a backup of the
current Mac's shortcuts and compare them with the managed configuration:

```sh
macos-shortcuts export ~/Desktop/mac-shortcuts-before.json
macos-shortcuts diff ~/.config/macos-shortcuts/shortcuts.json
```

`export` writes the current shortcut settings to the specified JSON file.
`diff` displays differences for the keys declared in the managed
configuration. Edit the source JSON in chezmoi to change the shared defaults.

## Apply on another Mac

Follow the repository's
[synchronization workflow](../setup.md#already-configured-mac-synchronize-safely)
to update the managed CLI and JSON file. Review the differences, then apply:

```sh
macos-shortcuts diff ~/.config/macos-shortcuts/shortcuts.json
macos-shortcuts apply ~/.config/macos-shortcuts/shortcuts.json --yes
```

The `--yes` flag explicitly authorizes preference changes for the current
macOS user. App shortcuts are updated individually. System, Services, and
Accessibility shortcut changes are merged into freshly exported preference
domains, preserving their other settings. Apply after finishing any edits in
System Settings to keep the imported configuration consistent.

Relaunch affected applications to activate updated menu shortcuts. Some
system-wide shortcuts take effect after logging out and back in. Keep the
exported JSON backup for reviewing or restoring previous bindings.
