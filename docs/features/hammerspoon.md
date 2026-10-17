# Hammerspoon shortcuts

[← Features](README.md) · [Development](../development.md)

Chezmoi owns the live Hammerspoon configuration at `~/.hammerspoon/`. The shared
modules implement display movement, Spaces, window selection, app-specific
shortcuts, and Rectangle layout bindings. The **personal** profile additionally
enables the SteelSeries audio check with `ctrl+alt+cmd+ä`.

| Component | Managed source |
| --- | --- |
| Entry point and profile condition | [`home/dot_hammerspoon/init.lua.tmpl`](../../home/dot_hammerspoon/init.lua.tmpl) |
| Shared behavior | [`home/dot_hammerspoon/modules/`](../../home/dot_hammerspoon/modules/) |
| Personal audio check | [`home/dot_hammerspoon/audio_check.lua`](../../home/dot_hammerspoon/audio_check.lua), [`audio_check_impl.lua`](../../home/dot_hammerspoon/audio_check_impl.lua) |
| Microphone meter | [Swift source and lazy compiler wrapper](../../home/dot_hammerspoon/bin/) |
| Personal-only exclusion | [`home/.chezmoiignore.tmpl`](../../home/.chezmoiignore.tmpl) |
| One-time legacy migration | [`home/run_once_before_05-migrate-hammerspoon.sh`](../../home/run_once_before_05-migrate-hammerspoon.sh) |
| Hammerspoon installation | [`src/apps.sh`](../../src/apps.sh) |

The microphone helper is built from its Swift source on first use via
`swiftc`, then cached in `~/.cache/hammerspoon/mic_level`. Neither a
machine-specific executable nor diagnostic logs are committed. The headphone
and camera names in the personal audio check are configurable source values.

## Migrate an already configured Mac

Follow [the existing-Mac workflow](../setup.md#already-configured-mac-synchronize-safely):
inspect Git state, merge the approved branch, preview `chezmoi diff`, and
**explicitly** run `chezmoi apply`. The once-before hook saves existing
`~/.hammerspoon` and `~/.hammerspoon-local` to
`~/Library/Application Support/dotfiles/backups/`, then removes *only*
recognized legacy AgentDesk skill symlinks for `init.lua`, `modules`, and
`bin`. Other files such as `Spoons/` are preserved. Unknown symlinks stop
the migration rather than being overwritten.

The former AgentDesk Hammerspoon skill assets can remain installed for other
purposes, but **do not rerun its `install-hammerspoon-config.sh` installer**:
it would replace the chezmoi-managed files with skill symlinks again. Future
Hammerspoon changes belong in this repository.

## First run and verification

Hammerspoon is installed by the shared application setup, but macOS permissions
require a local user action. Launch it once with `open -a Hammerspoon`, approve
Accessibility and microphone access as needed, then reload with
`ctrl+alt+cmd+r`. The configuration enables Hammerspoon at login.

Check read-only runtime information with:

```sh
/opt/homebrew/bin/hs -c 'return tostring(hs.accessibilityState()) .. "|" .. tostring(hs.autoLaunch()) .. "|" .. tostring(#hs.hotkey.getHotkeys())'
```

Then verify shortcuts on disposable windows and test the audio check with the
actual device. Unit, profile, and isolated-lifecycle tests cannot establish
that GUI moves, microphone permission, or microphone sensitivity work on a
physical Mac; don't run those intrusive tests on a working machine remotely.
