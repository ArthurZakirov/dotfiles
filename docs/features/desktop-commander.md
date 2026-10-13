# Desktop Commander remote

[← Features](README.md) · [How it works](../architecture.md)

On **personal macOS profiles**, dotfiles installs the `@wonderwhy-er/desktop-commander`
npm CLI and manages a user-level macOS LaunchAgent to run `desktop-commander remote`
after login. The professional profile does not manage this LaunchAgent.

| Component | Managed source |
| --- | --- |
| npm CLI installation | [`src/apps.sh`](../../src/apps.sh) (`install_desktop_commander_cli`) |
| Login service plist | [`home/private_Library/private_LaunchAgents/com.arthur.desktop-commander-remote.plist.tmpl`](../../home/private_Library/private_LaunchAgents/com.arthur.desktop-commander-remote.plist.tmpl) |
| Bootstrap and reload | [`home/run_after_20-ensure-desktop-commander-launch-agent.sh.tmpl`](../../home/run_after_20-ensure-desktop-commander-launch-agent.sh.tmpl) |
| Profile exclusion | [`home/.chezmoiignore.tmpl`](../../home/.chezmoiignore.tmpl) |

The plist uses the architecture-specific Homebrew binary path, `RunAtLoad` and
`KeepAlive`. Logs go to `~/Library/Logs/desktop-commander-remote*.log`.
The after-apply hook registers a missing service, leaves an existing service
running on first adoption, and reloads it only when a *previously managed*
plist changes. A SHA-256 marker in `~/Library/Caches/chezmoi` tracks the last
managed version. CI optional-app provisioning skips activation.

Inspect service status using
`launchctl print gui/$(id -u)/com.arthur.desktop-commander-remote`.
Running `chezmoi update` applies future changes explicitly; no credentials,
remote connection data, or machine-local authentication material is tracked.
This migration supersedes the archived pilot in
[AgentDesk](https://github.com/ArthurZakirov/AgentDesk/tree/chore/park-dotfiles-extras/experiments/parked-dotfiles);
it intentionally does **not** restore that pilot's placeholder `CLAUDE.md`.
