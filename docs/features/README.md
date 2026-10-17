# 🧩 Shared features

[← How it works](../architecture.md)

These capabilities are installed and synchronized through the same
[setup workflow](../setup.md). Feature pages describe what each capability does,
how to use it, and which files manage it.

## ChatGPT

- **[Desktop Commander remote](desktop-commander.md)** — Remote access to the personal Mac through a managed LaunchAgent.
- **[Local Agent Skills](chatgpt-skills-mcp.md)** — Read-only access to installed skills through an OpenAI Secure MCP Tunnel.

## Software engineering

- **[Git review](git-review.md)** — Commit and branch diffs in disposable review folders.
- **[Python environments](pysetup.md)** — Poetry-lock-based checkout-local virtual environments via `pysetup`.

## Shared infrastructure

- **[Zsh configuration](zsh.md)** — Shared prompt, history, completion, search, and shell plugins.
- **[Application provisioning](applications.md)** — Missing applications and CLI tools installed for each profile.
- **[Secrets management](secrets-management.md)** — Reusable credential lookup for independent personal-profile integrations.

To change or add a feature, follow the [development workflow](../development.md).
