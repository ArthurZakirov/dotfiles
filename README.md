# DevMac

**An opinionated, AI-ready development experience for macOS.**

AI agents can write code faster than you can review it. When inspecting the changes means setting up an environment, digging through files, and jumping between apps, it's tempting to skim a diff and approve. DevMac brings the tools and shortcuts together to make the work worth doing—and to make switching between windows, displays, and Macs just as easy.

## What DevMac makes effortless

### 🤖 Let agents complete tasks without babysitting

Give an agent a task without becoming its copy-paste assistant. DevMac equips it to inspect files, use browser and desktop apps, and consult proven instructions—so it can work through multi-step tasks while you do something else, involving you when approval or judgment is needed.

| Capability | Detailed feature documentation |
| --- | --- |
| Work through browser pages and supported Electron apps | [Agent Browser](docs/features/agent-browser.md) |
| See and control native macOS interfaces | [Peekaboo](docs/features/peekaboo.md) |
| Inspect files and run authorized local commands remotely | [Desktop Commander](docs/features/desktop-commander.md) (personal profile) |
| Read locally installed Agent Skills from ChatGPT | [Local Agent Skills via MCP](docs/features/chatgpt-skills-mcp.md) (personal profile) |
| Start with field-tested Codex guidance and hooks | [Codex configuration](docs/features/codex.md) |

[Agent capabilities, practical workflow, and usage limits →](docs/workflows/agent-capabilities.md)

### 🔎 Make keeping up with your agents' work effortless

An agent can finish a change before you've even opened the first diff. When getting to the relevant code, tests, and context takes too many steps, a thorough review is often replaced by a quick skim—allowing mistakes and unreviewed changes to reach a pull request or even production.

| Capability | Detailed feature documentation |
| --- | --- |
| Inspect changes in isolated, editable VS Code review workspaces | [Git review](docs/features/git-review.md) |
| Prepare Python environments for review checkouts | [Python environments](docs/features/pysetup.md) |
| Open repositories and configuration files quickly | [Raycast navigation](docs/features/raycast.md) |
| Find shell commands and history with fewer keystrokes | [Zsh](docs/features/zsh.md) |
| Control apps, windows, and Spaces from the keyboard | [Hammerspoon](docs/features/hammerspoon.md) · [macOS keyboard shortcuts](docs/features/macos-shortcuts.md) |

[Code review and fast navigation →](docs/workflows/review-and-navigation.md)

### 🖥️ Switch effortlessly between windows, monitors, and Macs

When reaching another window, screen, or computer feels like a chore, it is easier to stay where you are—even when the other workspace would be more useful.

| Capability | Related tools / documentation |
| --- | --- |
| Switch windows and arrange them on one screen | AltTab · Rectangle · [Hammerspoon](docs/features/hammerspoon.md) |
| Move between monitors and Spaces | [Hammerspoon](docs/features/hammerspoon.md) · DisplayLink |
| Improve scaling and text readability | BetterDisplay |
| Switch monitor inputs and move between computers | DDPM · Logi Options+ · [Shared configurations](docs/setup.md) |

[Window, display, and multi-Mac workflows →](docs/workflows/workspace-control.md)

## Explore

| Want to… | Go to |
| --- | --- |
| Find a particular capability and its detailed instructions | [Feature index](docs/features/README.md) |
| See which apps, CLIs, and configurations are included | [Tool inventory](docs/tool-inventory.md) |
| Install DevMac on a Mac or safely sync an existing Mac | [Setup guide](docs/setup.md) |
| Understand what gets installed, changed, or started | [Architecture and safety](docs/architecture.md) |
| Change configurations, contribute, and run tests | [Development workflow](docs/development.md) |

## Get started

For a new, unconfigured macOS machine, follow the [setup guide](docs/setup.md) for the installation command, profile selection, permissions, and verification. **If you already use chezmoi or have existing local configuration, inspect it before applying changes.**

After setup, explore the [feature index](docs/features/README.md) and complete any relevant permissions or account connections described in the feature guides.
