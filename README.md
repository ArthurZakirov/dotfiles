# DevMac

**An opinionated, AI-agent-ready development experience for macOS.**

AI agents can write code faster than you can review it. When inspecting their changes means setting up a local environment, digging through repositories and files, and jumping between Chrome tabs and apps, it's tempting to skim a diff and submit a PR. DevMac brings the tools and shortcuts together to make that tedious work effortless.

**Contents**

- [🧩 Features: How DevMac makes your work effortless](#-features-how-devmac-makes-your-work-effortless)
  - [🤖 Let agents work across systems without consuming your attention](#-let-agents-work-across-systems-without-consuming-your-attention)
  - [🔎 Make keeping up with your agents' work effortless](#-make-keeping-up-with-your-agents-work-effortless)
  - [🖥️ Switch effortlessly between monitors, Macs, operating systems, and your phone](#-switch-effortlessly-between-monitors-macs-operating-systems-and-your-phone)
- [🧭 Explore](#-explore)
- [🚀 Get started](#-get-started)

## 🧩 Features: How DevMac makes your work effortless

### 🤖 Let agents work across systems without consuming your attention

Give an agent a task without becoming its copy-paste assistant. DevMac equips it to inspect files, use browser and desktop apps, and consult proven instructions—so it can work through multi-step tasks while you do something else, involving you when approval or judgment is needed. The [ChatGPT personalization instructions](docs/features/chatgpt-personalization.md) tell ChatGPT how to access Desktop Commander and local Agent Skills; paste them manually during setup.

| Capability | Detailed feature documentation |
| --- | --- |
| 🌐 Work in browser sessions, including accounts authenticated for the agent | [Agent Browser](docs/features/agent-browser.md) |
| 🖥️ See and control native macOS interfaces and desktop apps | [Peekaboo](docs/features/peekaboo.md) |
| ◼️ Inspect files and run authorized commands on your Mac from a connected remote assistant | [Desktop Commander](docs/features/desktop-commander.md) |
| 📚 Let a connected ChatGPT assistant read locally installed Agent Skills | [Local Agent Skills via MCP](docs/features/chatgpt-skills-mcp.md) |
| ⚙️ Use field-tested [`AGENTS.md`](AGENTS.md), Codex configuration, and hooks to guide agent behavior | [Codex configuration](docs/features/codex.md) |

Desktop Commander remote access and the ChatGPT skills bridge are personal-profile capabilities and require explicit authorization.

[Agent capabilities, practical workflow, and usage limits →](docs/workflows/agent-capabilities.md)

### 🔎 Make keeping up with your agents' work effortless

An agent can finish a change before you've even opened the first diff. When getting to the relevant code, tests, and context takes too many steps, a thorough review is often replaced by a quick skim of the PR in the browser—allowing AI slop and mistakes to reach colleagues or even production.

| Capability | Detailed feature documentation |
| --- | --- |
| 🔴🟢 Review committed changes in VS Code diff tabs, with code navigation where supported | [Git review](docs/features/git-review.md) |
| 🐍 Set up Python environments for review checkouts with a single command | [Python environments](docs/features/pysetup.md) |
| 🔄 Refresh permanent checkouts and rebase feature branches, preserving unfinished work | [Automatic repository refresh](docs/features/repo-refresh.md) |
| 📁 Find Git repositories and frequently used config files, then open them in VS Code | [Raycast navigation](docs/features/raycast.md) (one-time Raycast setup) |
|  Open the right app or window on the right monitor with a keyboard shortcut | Raycast ([tool inventory](docs/tool-inventory.md#desktop-applications-homebrew-casks)) · [Hammerspoon](docs/features/hammerspoon.md) · [macOS keyboard shortcuts](docs/features/macos-shortcuts.md) · AltTab · Rectangle |
| ◼️ Find and reuse shell commands without memorizing them or making typos | [Zsh](docs/features/zsh.md) |

[Code review and fast navigation →](docs/workflows/review-and-navigation.md)

### 🖥️ Switch effortlessly between monitors, Macs, operating systems, and your phone

When moving to another monitor or computer feels like a chore, it's easier to stay in the wrong workspace. DevMac combines display controls, shortcuts, and portable configuration to make switching so frictionless, that you use the right tool for the job.

| Capability | Related tools / documentation |
| --- | --- |
| 🖥️🖥️ Move windows and focus between monitors | [Hammerspoon](docs/features/hammerspoon.md) · DisplayLink |
| 👁️ Improve display sharpness and text readability | BetterDisplay |
| 💻💻 Switch computers and carry your setup across Macs | DDPM · Logi Options+ · [Git and chezmoi setup](docs/setup.md) |
| 💻📱 Control your Mac remotely from another device | *Guide coming soon* |
| 🪟🍎 Work across Windows, WSL2, and macOS | *Guide coming soon* |

[Window, display, and multi-Mac workflows →](docs/workflows/workspace-control.md)

## 🧭 Explore

| Want to… | Go to |
| --- | --- |
| 💪 Find a particular capability and its detailed instructions | [Feature index](docs/features/README.md) |
| 🛠️ See which apps, CLIs, and configurations are included | [Tool inventory](docs/tool-inventory.md) |
| 🚀 Install DevMac on a Mac or safely sync an existing Mac | [Setup guide](docs/setup.md) |
| 🔎 Understand what gets installed, changed, or started | [Architecture and safety](docs/architecture.md) |
| 👷 Change configurations, contribute, and run tests | [Development workflow](docs/development.md) |

## 🚀 Get started

1. For a new, unconfigured macOS machine, follow the [setup guide](docs/setup.md) for the installation command, profile selection, permissions, and verification. **If you already use chezmoi or have existing local configuration, inspect it before applying changes.**

2. After setup, explore the [feature index](docs/features/README.md) and complete any relevant permissions or account connections described in the feature guides.
