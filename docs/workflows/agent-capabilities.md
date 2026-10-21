# Let agents complete tasks without babysitting

[← DevMac](../../README.md) · [Feature index](../features/README.md) · [Tool inventory](../tool-inventory.md)

## From conversation to action

A task stalls when the agent needs you to copy a file, click through an app, retrieve a document, or explain how a tool works. With access to the right files, browser and desktop interfaces, and reusable instructions, a connected agent can carry out more of the workflow itself while you work on something else. Human approval, credentials, and decisions still matter when the task requires them.

| When an agent needs to… | DevMac supplies | How it works |
| --- | --- | --- |
| Read files, inspect processes, or run authorized commands on your Mac | [Desktop Commander remote](../features/desktop-commander.md) | A remote-access CLI and login service on the **personal** profile; requires an authorized connection |
| Navigate browser pages or supported Electron apps | [Agent Browser](../features/agent-browser.md) | A CLI with its own browser runtime and an installed **Codex** skill |
| Observe and operate native macOS windows | [Peekaboo](../features/peekaboo.md) | macOS accessibility and screen-capture tooling, plus a **Codex** skill |
| Find instructions already installed on the Mac | [Local Agent Skills in ChatGPT](../features/chatgpt-skills-mcp.md) | A **read-only** MCP server through a configured tunnel on the **personal** profile |
| Follow consistent coding conventions and hooks | [Codex configuration](../features/codex.md) | Managed guidance and selected shared Codex settings; not an alternative execution engine |

These mechanisms are complementary, **not interchangeable**. Installing a CLI or skill does not give every ChatGPT conversation access to it. ChatGPT needs an actual connected tool/remote pathway; Codex can use its own installed skills and local executables. macOS permissions, supported apps, authenticated accounts, and user approvals still apply.

## Why this matters when agent usage is constrained

Specialized coding agents can consume their included usage allowance on large or repeated tasks. Ordinary ChatGPT conversations and Codex/Work have **different usage accounting**, so a tool-enabled chat can sometimes remain a useful way to inspect, research, and perform supervised actions without starting another Codex/Work task.

The practical advantage is **another way to get work done with tools already available to your ChatGPT plan**, not an unlimited-token loophole. ChatGPT has model, feature, tool, and fair-use limits of its own. Work and Codex can share an agentic usage allowance, and neither has a fixed unlimited token entitlement. There is no verified fixed euro-to-token saving or guarantee that a long-running task will continue indefinitely.

Current primary sources: [Codex and plan usage](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan), [ChatGPT model limits](https://help.openai.com/en/articles/20001354-gpt-6-and-other-models-in-chatgpt), and [credit-based agentic usage](https://help.openai.com/en/articles/12642688-using-credits-for-flexible-usage-in-chatgpt-personal-plans).

## Example: verify an agent's change

1. Ask the connected assistant to **inspect** the relevant files or repository state with an authorized remote tool; do not assume a suggested change was applied.
2. Use browser automation for supported web interfaces, or native UI automation when a real Mac app must be inspected.
3. Ask it to load an applicable local skill when specific operating instructions would improve the result.
4. Review the observed state or code diff yourself. A successful tool invocation is **not** evidence that the intended application outcome occurred.

### Boundaries

- Only the **personal** profile provisions the Desktop Commander remote service and ChatGPT local-skills bridge; other tools may be installed on both profiles.
- The local-skills bridge is read-only for skill files, but **skill content you request is transmitted to ChatGPT**. Do not expose private instructions or employer data unintentionally.
- Remote command and UI-control capabilities can affect real files and live applications. Restrict access, inspect proposed commands, and keep human approval for consequential operations.
- This setup augments ChatGPT; it does **not** turn ordinary chat into an identical replacement for the managed Codex or ChatGPT Work execution environments.

[Return to the full feature index →](../features/README.md)
