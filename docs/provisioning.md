# Application provisioning (implementation)

[← Architecture](architecture.md) · [Tool inventory](tool-inventory.md) · [Features](features/README.md)

**Source of truth:** [`dependencies/`](../dependencies/) holds all machine-provisioning
package identities, profile assignments, classifications, version pins, and
declared post-install actions. The installer scripts implement behavior, not
package/profile membership.

## Dependency inventories

| Profile | Homebrew CLI | Homebrew GUI | npm global CLI | Other |
| --- | --- | --- | --- | --- |
| Common (both profiles) | [`common/cli.Brewfile`](../dependencies/brew/common/cli.Brewfile) | [`common/gui.Brewfile`](../dependencies/brew/common/gui.Brewfile) | [`common.txt`](../dependencies/npm/common.txt) | [`Git pins`](../dependencies/git/common/) |
| Personal only | [`personal/cli.Brewfile`](../dependencies/brew/personal/cli.Brewfile) | [`personal/gui.Brewfile`](../dependencies/brew/personal/gui.Brewfile) | [`personal.txt`](../dependencies/npm/personal.txt) | [`Manual installers`](../dependencies/manual/personal.txt) |

Move a package between profile inventories to change its scope. All packages
use the same idempotent install-on-missing behavior. The Python entry also declares `min-version: 3.11`; an older system `python3` does not satisfy that manifest requirement. There is no separate
`required` or `optional` package mode, and no skip-optional-apps flag.

## Execution and lifecycle

| Source | Responsibility |
| --- | --- |
| [`src/homebrew.sh`](../src/homebrew.sh) | Bootstraps Homebrew if absent. |
| [`src/shell-setup.sh`](../src/shell-setup.sh) | Installs common CLI/GUI/npm, Git pins, then profile-specific tools. |
| [`src/apps.sh`](../src/apps.sh) | Reads Homebrew and npm manifests; detects existing executable, formula receipts, casks and app bundles before installing. |
| [`src/setup-actions.sh`](../src/setup-actions.sh) | Implements package-specific post-install actions without determining profile membership. |
| [`src/agent-skills.sh`](../src/agent-skills.sh) | Validates supported upstream agent skills. |
| [`home/`](../home/) | Managed configuration, hooks and macOS LaunchAgents. |

The official chezmoi bootstrap installer supplies `chezmoi` before the managed
installer first runs. Git and the remaining shell tools live in the same
common CLI inventory as other command-line tools. The existing binary or
Homebrew receipt is checked before any package installation: no routine
`brew bundle` download is required merely to inspect these tools. npm and
Homebrew post-install actions execute even if the package already exists.

Swift for Hammerspoon's microphone diagnostics is a **feature runtime**, not a
separate installation policy: its compiler is checked and provisioned only when
the diagnostics require it. Its manifest remains with that feature at
[`common/features/hammerspoon-swift.Brewfile`](../dependencies/brew/common/features/hammerspoon-swift.Brewfile).

CI separates real profile rendering (`chezmoi apply --exclude scripts` against
an ephemeral HOME) from installer unit tests, which use stubs. It does not
change the semantics of a user's `chezmoi apply`. Global npm tools remain
global, not project-local `package.json` installs.

## What the installer does not do

Installing a package does **not** automatically enable macOS Accessibility and Screen Recording permissions, Logitech Flow, monitor input shortcuts, Raycast Store extensions, provider logins, ChatGPT plugin connections, or machine-local secrets. For Raycast, chezmoi manages file-opening Script Commands and opens the Repository Manager Store page once, but Raycast still requires manual extension installation and Script Command registration ([details](features/raycast.md)). Some feature hooks do additional work; inspect them in the [architecture](architecture.md) and follow the [relevant feature instructions](features/README.md).

For an already configured Mac, follow the
[safe synchronization workflow](setup.md#already-configured-mac-synchronize-safely).
Chezmoi hooks can have side effects even when destination files have not changed.
