# What DevMac installs and manages

[← DevMac](../README.md) · [Features by purpose](features/README.md) · [Architecture](architecture.md)

Browse the software behind DevMac by component type and installation method. For the workflows these components enable, see the [feature index](features/README.md).

**Scope:** `shared` = personal and professional profiles; `personal` = personal profile only. An app being declared for installation does not mean its settings, accounts, or entire runtime are managed. `Brewfile`, [`src/apps.sh`](../src/apps.sh), [`src/shell-setup.sh`](../src/shell-setup.sh), and the linked managed sources are authoritative; this is a readable snapshot of their intent.

## Desktop applications (Homebrew casks)

| Application | Scope | Why it is here |
| --- | --- | --- |
| AltTab | Shared | [Window switching](workflows/workspace-control.md) |
| BetterDisplay | Shared | [Scaling and readable displays](workflows/workspace-control.md) |
| DisplayLink Manager | Shared | [External display support](workflows/workspace-control.md), with compatible hardware |
| DDPM | Shared | [Dell monitor input switching](workflows/workspace-control.md) |
| Rectangle | Shared | [Window placement](workflows/workspace-control.md) |
| Hammerspoon | Shared | [Managed window, Spaces, and application hotkeys](features/hammerspoon.md) |
| Logi Options+ | Shared | [Mouse/keyboard workflows, including compatible Flow setups](workflows/workspace-control.md) |
| Logi Tune | Shared | Logitech device and audio settings |
| Raycast | Shared | Application launcher and search |
| Warp | Shared | Terminal for shell-based workflows |
| Visual Studio Code | Shared | [Review workspace and diff navigation](features/git-review.md) |
| Google Chrome | Shared | Web navigation and developer workflows |
| Google Drive | Shared | Files accessible through the provider's desktop app |
| Docker Desktop | Shared | Containerized development |
| ChatGPT | Shared | Chat assistant; [agent tool integration](workflows/agent-capabilities.md) requires a separate connection |
| Claude desktop | Shared | Desktop AI assistant; no DevMac-specific runtime orchestration is implied |
| Bitwarden | Personal | Credential management for supported integrations |
| Notion, Todoist, Telegram, WhatsApp | Personal | General-purpose personal applications, not bespoke DevMac features |

Homebrew installs or detects these applications. **DevMac does not configure every app**, account, device, or extension automatically. Most entries are delivered by [`src/apps.sh`](../src/apps.sh).

## Command-line tools (Homebrew)

| Tool / source | Scope | Purpose |
| --- | --- | --- |
| `chezmoi` (`Brewfile`) | Shared | Declarative file management and apply lifecycle |
| `git` (`Brewfile`) | Shared | Versioning, repository navigation, and review |
| `fzf` (`Brewfile`) | Shared | Fast interactive shell search |
| `zsh-autosuggestions`, `zsh-syntax-highlighting` (`Brewfile`) | Shared | [Shell recall and readability](features/zsh.md) |
| `python`, `uv` (`Brewfile`) | Shared | Python tooling and [review environments](features/pysetup.md) |
| Codex CLI (cask) | Shared | Coding agent with [managed guidance](features/codex.md) |
| Claude Code CLI (cask) | Shared | Another coding-agent option; not required for ChatGPT tools |
| Node.js / npm (formula) | Shared | Runtime for installed browser/skill CLIs |
| Peekaboo (formula via tap) | Shared | [Native macOS computer use](features/peekaboo.md) |
| `xurl` (cask) | Personal | URL opening/dispatch CLI |
| `langsmith` (formula via tap) | Personal | Personal integration tooling |
| `tunnel-client` (formula via tap) | Personal | [Secure MCP tunnel transport](features/chatgpt-skills-mcp.md) |

These tools are installed from the [Brewfile](../Brewfile) or through [`src/apps.sh`](../src/apps.sh). Some use third-party taps.

## npm global CLIs

| Package | Scope | Purpose |
| --- | --- | --- |
| `agent-browser` | Shared | [Browser and supported Electron automation](features/agent-browser.md) |
| `skills` (used by `npx skills`) | Shared | Install and maintain selected [agent skills](features/agent-browser.md) |
| `@wonderwhy-er/desktop-commander` | Personal | [Remote command/file tooling](features/desktop-commander.md) |

DevMac installs these through [`src/apps.sh`](../src/apps.sh), not the Brewfile. The official **Peekaboo** and **Agent Browser** skills are installed and validated through `npx skills`, separately from the CLI binaries.

## Direct bootstrap and upstream installations

| Component | Scope | Source and installation method | Purpose |
| --- | --- | --- | --- |
| Bitwarden Secrets Manager CLI (`bws`) | Personal | [`src/shell-setup.sh`](../src/shell-setup.sh) downloads and runs the [upstream shell installer](https://bws.bitwarden.com/install) if `bws` is missing | [Retrieve runtime secrets](features/secrets-management.md) for personal integrations |
| Oh My Zsh | Shared | [`src/shell-setup.sh`](../src/shell-setup.sh) clones the upstream repository and checks out the revision pinned in [`home/.chezmoidata.toml`](../home/.chezmoidata.toml) | [Zsh framework](features/zsh.md) |
| Homebrew bootstrap | Shared | [`src/homebrew.sh`](../src/homebrew.sh) installs Homebrew if absent | Install formulae and casks listed above |

Unlike optional application provisioning, the `bws` installation also runs for personal profiles when `DOTFILES_SKIP_OPTIONAL_APPS=1`.

## Managed configurations, scripts, and services

| Kind | DevMac-managed component | Purpose / details |
| --- | --- | --- |
| Shell template | Zsh startup settings, Git aliases | [Fast shell navigation](features/zsh.md) · [Git review](features/git-review.md) |
| Local scripts / VS Code integration | Git review, `pysetup`, review UI extension | [Review and isolated Python checkouts](workflows/review-and-navigation.md) |
| Hammerspoon Lua + activation | Hotkeys, display movement, Spaces, audio checks | [Hammerspoon](features/hammerspoon.md) |
| macOS preference import/export | Native system, application, service shortcuts | [macOS shortcuts](features/macos-shortcuts.md) |
| Codex guidance, hooks, selected settings | Codex behavior and prompt customization | [Codex](features/codex.md); other local Codex settings remain unmanaged |
| LaunchAgent + remote CLI | Desktop Commander at login | [Personal remote access](features/desktop-commander.md) |
| LaunchAgent + Python MCP server + tunnel client | Read installed Agent Skills through ChatGPT | [Personal skills bridge](features/chatgpt-skills-mcp.md) |
| Credential lookup helper | Machine-local secret retrieval | [Bitwarden Secrets Manager setup](features/secrets-management.md) |

**Not installed as a silent managed configuration:** Raycast Store extensions and local Quicklinks; Logitech Flow pairing; monitor input mappings; macOS privacy approvals; ChatGPT plugin/tunnel registration; provider logins; secrets themselves. Refer to the linked feature pages for manual steps.

## Where to audit behavior

- [Application provisioning](provisioning.md): package checks and profile-specific install flow.
- [Architecture](architecture.md): chezmoi templates, hooks, backup/synchronization behavior, and CI coverage.
- [Setup and safety](setup.md): inspect an existing Mac before `apply`; hooks may install software or start services.
- [Development](development.md): modify the configuration and verify its effects without applying changes blindly.
