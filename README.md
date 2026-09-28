# Dotfiles

Managed with [chezmoi](https://www.chezmoi.io/).

## Desktop Commander Remote on macOS

This repository keeps the Desktop Commander Remote background service reproducible and inspectable:

- [LaunchAgent template](private_Library/private_LaunchAgents/com.arthur.desktop-commander-remote.plist.tmpl) defines the macOS service.
- [Install hook](run_before_10-install-desktop-commander.sh) ensures the pinned Desktop Commander package is installed.
- [Launch hook](run_after_20-ensure-desktop-commander-launch-agent.sh) validates and loads the service, reloading it only when the rendered plist changes.
- [.chezmoiignore.tmpl](.chezmoiignore.tmpl) keeps the macOS LaunchAgent out of non-macOS targets.

Run `chezmoi diff` to preview changes and `chezmoi apply` to converge the machine to the repository state.

Inspect the live service with:

```sh
launchctl print "gui/$(id -u)/com.arthur.desktop-commander-remote"
```

Authentication/session material is intentionally **not** stored in this repository. A fresh Mac therefore needs the Desktop Commander OAuth flow completed once; the persisted local session can then be reused by the LaunchAgent.

The service's executable, environment, restart policy, and log destinations are canonical in the [LaunchAgent template](private_Library/private_LaunchAgents/com.arthur.desktop-commander-remote.plist.tmpl), rather than duplicated here.
