# Application provisioning (implementation)

[← Architecture](architecture.md) · [Tool inventory](tool-inventory.md) · [Features](features/README.md)

**Source of truth:** [`dependencies/`](../dependencies/) holds all machine-provisioning
package identities, profile assignments, classifications, version pins, and
declared post-install actions. The installer scripts implement behavior, not
package/profile membership.

## Dependency inventories

| Scope | Homebrew CLI | Homebrew GUI | npm global CLI | Other |
| --- | --- | --- | --- | --- |
| Required, both profiles | [`required.Brewfile`](../dependencies/brew/required.Brewfile) | — | — | [`Git pins`](../dependencies/git/common/) |
| Optional, both profiles | [`common/cli.Brewfile`](../dependencies/brew/common/cli.Brewfile) | [`common/gui.Brewfile`](../dependencies/brew/common/gui.Brewfile) | [`common.txt`](../dependencies/npm/common.txt) | — |
| Optional, personal | [`personal/cli.Brewfile`](../dependencies/brew/personal/cli.Brewfile) | [`personal/gui.Brewfile`](../dependencies/brew/personal/gui.Brewfile) | [`personal.txt`](../dependencies/npm/personal.txt) | [`Manual installers`](../dependencies/manual/personal.txt) (required regardless of optional-app skip) |
| On demand, both profiles | [`Swift Brewfile`](../dependencies/brew/common/on-demand/hammerspoon-swift.Brewfile) | — | — | — |

Move an entry between the appropriate inventory files to change profile
membership. A new professional-only inventory can be placed under the
corresponding `professional/` directory. The shell runner discovers profiles
by scope instead of hardcoding package lists.

## Execution and lifecycle

| Source | Responsibility |
| --- | --- |
| [`src/homebrew.sh`](../src/homebrew.sh) | Bootstraps Homebrew if absent. |
| [`src/shell-setup.sh`](../src/shell-setup.sh) | Orchestrates required packages, optional packages, Git pins and manual installers in the established order. |
| [`src/apps.sh`](../src/apps.sh) | Reads optional Homebrew and npm manifests; detects existing executables and application bundles. |
| [`src/setup-actions.sh`](../src/setup-actions.sh) | Implements package-specific installation and post-install actions without determining profile membership. |
| [`src/agent-skills.sh`](../src/agent-skills.sh) | Validates supported upstream agent skills. |
| [`home/`](../home/) | Managed configuration, hooks and macOS LaunchAgents. |

The required Brewfile is installed on every apply. When
`DOTFILES_SKIP_OPTIONAL_APPS=1`, Homebrew and npm optional dependencies are
skipped; required Git and manual dependencies retain their original behavior.
npm manifest entries may specify a post-install action. Homebrew annotations
may specify a post-install action after the package detection step. Actions
run even if the corresponding binary or application already existed.

On-demand Swift provisioning reads the canonical Brewfile from the active
chezmoi source checkout, rather than maintaining a second copy under `home/`.
Global npm tools remain global (not project-local `package.json` installs).
Project-specific Python dependency files stay with their owning projects.

## What the installer does not do

Installing a package does **not** automatically enable macOS Accessibility and Screen Recording permissions, Logitech Flow, monitor input shortcuts, Raycast Store extensions, provider logins, ChatGPT plugin connections, or machine-local secrets. For Raycast, chezmoi manages file-opening Script Commands and opens the Repository Manager Store page once, but Raycast still requires manual extension installation and Script Command registration ([details](features/raycast.md)). Some feature hooks do additional work; inspect them in the [architecture](architecture.md) and follow the [relevant feature instructions](features/README.md).

For an already configured Mac, follow the
[safe synchronization workflow](setup.md#already-configured-mac-synchronize-safely).
Chezmoi hooks can have side effects even when destination files have not changed.
