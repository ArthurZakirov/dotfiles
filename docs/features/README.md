# DevMac features

[← DevMac](../../README.md) · [Tool inventory](../tool-inventory.md)

Explore DevMac by workflow. Some tools support several different capabilities.

## Let agents complete tasks without babysitting

For ChatGPT, the [personalization instructions](chatgpt-personalization.md) tell the assistant how to access Desktop Commander and local Agent Skills. Paste them manually during setup.

[Why agents need these tools—and what ChatGPT usage limits mean →](../workflows/agent-capabilities.md)

| Capability | Detailed feature documentation |
| --- | --- |
| Work through browser pages and supported Electron apps | [Agent Browser](agent-browser.md) |
| See and control native macOS interfaces | [Peekaboo](peekaboo.md) |
| Inspect files and run authorized local commands remotely | [Desktop Commander](desktop-commander.md) (personal profile) |
| Read locally installed Agent Skills from ChatGPT | [Local Agent Skills via MCP](chatgpt-skills-mcp.md) (personal profile) |
| Start with field-tested Codex guidance and hooks | [Codex configuration](codex.md) |

## Review and navigate at agent speed

[Why easier access leads to better reviews →](../workflows/review-and-navigation.md)

| Capability | Detailed feature documentation |
| --- | --- |
| Inspect changes in isolated, editable VS Code review workspaces | [Git review](git-review.md) |
| Prepare Python environments for review checkouts | [Python environments](pysetup.md) |
| Find apps, repositories, and configuration files quickly | [Raycast navigation](raycast.md) |
| Find shell commands and history with fewer keystrokes | [Zsh](zsh.md) |
| Control apps, windows, and Spaces from the keyboard | [Hammerspoon](hammerspoon.md) · [macOS keyboard shortcuts](macos-shortcuts.md) |

## Switch windows, displays, and Macs

[Window management, multi-monitor, and multi-Mac workflows →](../workflows/workspace-control.md)

| Capability | Related tools / documentation |
| --- | --- |
| Switch windows and arrange them on one screen | AltTab · Rectangle · [Hammerspoon](hammerspoon.md) |
| Move between monitors and Spaces | [Hammerspoon](hammerspoon.md) · DisplayLink |
| Improve scaling and text readability | BetterDisplay |
| Switch monitor inputs and move between computers | DDPM · Logi Options+ · [Shared configurations](../setup.md) |

## Understand the implementation

Browse the [tool inventory](../tool-inventory.md) by package manager, GUI app, CLI, service, and configuration. For installation hooks and provisioning behavior, see [application provisioning](../provisioning.md) and [architecture](../architecture.md).

To customize DevMac, follow the [development workflow](../development.md).
