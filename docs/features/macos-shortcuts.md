# macOS keyboard shortcuts

[← Shared features](README.md) · [Development](../development.md)

Chezmoi synchronizes macOS keyboard shortcut overrides together with your
other dotfiles. The desired configuration is stored in
[`home/dot_config/macos-shortcuts/shortcuts.json`](../../home/dot_config/macos-shortcuts/shortcuts.json).

## Managed shortcuts

| Configuration | macOS preference | Synchronization |
| --- | --- | --- |
| `system_hotkeys` | `com.apple.symbolichotkeys` / `AppleSymbolicHotKeys` | Enabled states and key bindings by hotkey ID |
| `app_shortcuts` | `NSUserKeyEquivalents` | Menu shortcuts by application and menu title |
| `service_shortcuts` | `pbs` / `NSServicesStatus` | Shortcuts by Service ID |
| `accessibility_hotkeys` | `com.apple.universalaccess` / `UserAssignableHotKeys` | Shortcuts by accessibility-hotkey ID |

Each system and accessibility hotkey includes a readable `action` label
alongside its numeric ID and binding. For example:

```json
"64": {
  "action": "Spotlight: show search",
  "enabled": true
}
```

The numeric ID and binding define the native macOS behavior. The action label
is used for reading and reviewing JSON; the importer writes only native
preference fields. Labels come from a
[curated macOS hotkey ID mapping](https://gist.github.com/stephancasas/2c8e8f71e23ec7221495d7f4b9efb794)
and [LinearMouse's hotkey definitions](https://github.com/linearmouse/linearmouse/blob/main/Modules/KeyKit/Sources/KeyKit/SymbolicHotKey.swift).

Chezmoi preserves other preferences and locally configured shortcuts outside
the managed entries. Review numeric hotkey IDs when transferring configurations
between macOS versions or keyboard layouts.

## Review changes

```sh
chezmoi diff
```

Chezmoi compares the files it manages and opens their diffs in VS Code. Its
diff hook also reads your current macOS shortcut settings, compares the
managed entries against the repository's JSON, and opens a VS Code JSON diff
whenever the shortcuts differ. When VS Code is unavailable, the hook prints
a unified text diff, including with the
`chezmoi --no-pager --use-builtin-diff diff --exclude scripts` recovery command.

The shortcut diff shows **current Mac** on the left and **managed
configuration** on the right. To adopt a change made in macOS System Settings,
update the repository's `shortcuts.json` with the desired value.

## Apply changes

```sh
chezmoi apply
```

Chezmoi writes the managed files and then applies the desired keyboard
shortcuts to the current user's macOS preferences. The importer merges
individual app menu bindings and preserves unrelated preferences when
updating the system, Services, and Accessibility preference domains.

Run `chezmoi diff` before applying to review changes. Finish any simultaneous
keyboard-shortcut edits in System Settings before applying. Relaunch affected
applications to activate updated menu shortcuts; some system-wide shortcuts
take effect after logging out and back in.

The [standard synchronization workflow](../setup.md#already-configured-mac-synchronize-safely)
uses the same two chezmoi commands on each MacBook. When adopting this feature
on an already configured Mac, follow that workflow's one-time `chezmoi init`
step to regenerate the chezmoi configuration containing the diff hook.
