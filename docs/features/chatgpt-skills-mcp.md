# Local Agent Skills in ChatGPT (personal profile)

[← Features](README.md) · [Setup](../setup.md)

This personal-only integration exposes installed `~/.agents/skills` to normal
ChatGPT chats over a **read-only** FastMCP server and an OpenAI Secure MCP
Tunnel. It does not install, update, manage or depend on any skill repository or
skill installer.

```text
~/.agents/skills/ → local FastMCP → OpenAI tunnel → ChatGPT plugin
```

The MCP server offers `search_skills`, `read_skill` and
`read_skill_resource`. It reads the local files on each call, including
supported symlinked skill directories. Tool descriptions encourage discovery,
but ChatGPT ultimately decides which tool to call.

## Automated personal-Mac setup

The personal-profile dotfiles installer installs the tunnel client, FastMCP
runtime, and `local.skills.mcp` macOS LaunchAgent automatically. The
LaunchAgent starts at login and restarts after failures. A repeated
`chezmoi apply` leaves an unchanged service running; changing the managed
configuration restarts only that service.

The launcher obtains its API key from the [shared secrets infrastructure]
(secrets-management.md) rather than implementing a feature-specific credential
store. The server does not inherit that key. No passwords or API keys are kept
in Git, a LaunchAgent plist or command arguments.

Tunnel selection is **injected per machine**, never hardcoded: existing local
tunnel configuration takes precedence, with optional `OPENAI_TUNNEL_ID` from
the configured secret provider as fallback. The one-time prerequisite is an
existing OpenAI tunnel attached to the correct workspace, with a restricted
`OPENAI_TUNNEL_API_KEY` provisioned through the common secrets infrastructure.
Once available, dotfiles setup needs no feature-specific terminal commands or
manual launchctl action. Missing external account provisioning results in a
safe no-op, not a prompt or a broken service.

The first connection of a *new* custom MCP plugin to a ChatGPT account/workspace
still requires authorization through ChatGPT's own UI. An existing plugin does
not need updating when a local `SKILL.md` changes; if the MCP schema changes,
refresh the plugin's tool catalog.

## Scope and security

- **Personal profile only:** The professional profile does not install the
  server, secret helper, LaunchAgent or optional tunnel client.
- **Neutral service label:** `local.skills.mcp`. No computer/user/account name
  or tunnel ID is compiled into the code or plist.
- **Skill discovery:** Reads `~/.agents/skills/` by default, independent of how
  its directories are managed. `LOCAL_SKILLS_ROOT` overrides it for testing.
- **Resource access:** Reads only text-like files within a selected skill's
  `references/` directory; rejects traversal, hidden paths and symlinks
  escaping the selected skill. Files larger than 256 KB are rejected.
- **Communication:** Requested skill text is sent to ChatGPT. Store no secrets
  in skills exposed through this integration.
- **Runtime:** The Mac must be running with its user session logged in for
  the user LaunchAgent to provide the tunnel.
- **Troubleshooting:** Read the macOS LaunchAgent status and
  `~/Library/Logs/local-skills-mcp.err.log`. Credential retrieval failures
  report redacted errors without dumping backend output.

Existing local installations are migrated by the chezmoi after-hook without
requiring users to start or stop shell processes. The running predecessor is
preserved if the new service cannot start.

Official references: [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels),
[tunnel-client](https://github.com/openai/tunnel-client),
[FastMCP](https://gofastmcp.com/).
