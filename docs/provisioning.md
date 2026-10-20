# Application provisioning (implementation)

[← Architecture](architecture.md) · [Tool inventory](tool-inventory.md) · [Features](features/README.md)

DevMac uses Homebrew, npm, direct upstream installers, and managed configuration to assemble its developer environment. This page documents package detection, installation sources, and lifecycle behavior.

## Sources of truth

| Source | Responsibility |
| --- | --- |
| [`Brewfile`](../Brewfile) | Shared Homebrew CLI dependencies |
| [`src/apps.sh`](../src/apps.sh) | Detection and installation of shared and profile-specific applications/CLIs through Homebrew and npm |
| [`src/shell-setup.sh`](../src/shell-setup.sh) | Orchestrates setup; installs pinned Oh My Zsh and the personal-profile `bws` CLI directly |
| [`src/homebrew.sh`](../src/homebrew.sh) | Bootstraps Homebrew when it is missing |
| [`src/agent-skills.sh`](../src/agent-skills.sh) | Installation, provenance, and integrity checks for supported upstream agent skills |
| [`home/`](../home/) | Managed configuration, hooks, scripts, and macOS LaunchAgents |
| [Tool inventory](tool-inventory.md) | Human-readable breakdown by GUI app, package manager, CLI, and managed artifact |

When `DOTFILES_SKIP_OPTIONAL_APPS` is not `1`, both profiles run `install_common_apps`; the personal profile additionally runs `install_personal_apps`. Installation helpers check for existing executables or application bundles and skip recognized installations before invoking Homebrew or npm. Separately, the personal-profile setup installs `bws` through the [Bitwarden upstream installer](https://bws.bitwarden.com/install) when the CLI is missing: `src/shell-setup.sh` downloads the shell installer and executes it. This step is not controlled by `DOTFILES_SKIP_OPTIONAL_APPS`. Detection cannot prove an installed app is configured, authenticated, permitted, or working for the intended task.

## What the installer does not do

Installing a package does **not** automatically enable macOS Accessibility and Screen Recording permissions, Logitech Flow, monitor input shortcuts, Raycast Store extensions, provider logins, ChatGPT plugin connections, or machine-local secrets. Some feature hooks do additional work; inspect them in the [architecture](architecture.md) and follow the [relevant feature instructions](features/README.md).

Before applying DevMac on an already-configured Mac, follow the [safe synchronization workflow](setup.md#already-configured-mac-synchronize-safely). Apply hooks may have side effects even when destination files have not changed.
