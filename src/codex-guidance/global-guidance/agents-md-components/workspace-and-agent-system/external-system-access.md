<a id="external-system-access"></a>
# 🔌 External system access

Prefer structured, authenticated integrations over UI automation for account-backed systems. Use browser interaction as a fallback, not as the default access path.

| When | Then |
| --- | --- |
| A task requires reading from, writing to, or operating an account-backed external system such as GitHub, Jira, Notion, Gmail, Bitbucket, Databricks, or another authenticated service. | Before using browser automation, inspect the capabilities already available in the current runtime: native connectors, plugins, MCP tools, APIs, and installed or official CLIs. Prefer the narrowest structured interface that directly supports the task. |
| No suitable structured integration is currently available or connected. | Check whether an appropriate plugin, MCP integration, API path, or official CLI is discoverable and practical to use. If connection, setup, or authentication is the only blocker, ask the user to connect or authenticate through the supported flow rather than immediately falling back to browser automation. Do not install software, change credentials, or broaden permissions without the authorization required for that action. |
| A structured integration is unavailable, cannot perform the required operation, or remains blocked after the supported connection/authentication path is attempted or declined. | Use browser interaction as the fallback. When the runtime can control the user's regular Chrome profile and the task benefits from existing sessions, extensions, or password-manager access, prefer that Chrome profile over an isolated or in-app browser; otherwise use the available browser surface and state the limitation when it materially affects the task. |
| The task is ordinary public-web research that does not require the user's account, private data, or an authenticated action. | Use the most appropriate research/browser tooling directly; do not add integration-discovery or authentication work that does not help the task. |

When Codex on macOS needs the user's signed-in regular Chrome, use
`~/.local/bin/agent-chrome` with ordinary Agent Browser commands. Consult the
installed Agent Browser skill for command syntax. Use this entry point from
every chat and omit session, connection, and state persistence options. It uses
a fixed daemon session and attaches to running Chrome through Agent Browser's
auto-connect. Keep the shared daemon running between tasks.

The daemon shares its active tab and snapshot references across chats. Use a
dedicated task tab, verify the active tab and take a fresh snapshot before
acting, and coordinate so only one chat operates the shared session at a time.
Close only the task tab you opened.

Enable Chrome's remote debugging through `chrome://inspect/#remote-debugging`
when setting up the connection. If Chrome or its Agent Browser daemon restarts,
use the same entry point to reattach. Chrome may ask the user to allow the
connection again. If a connection fails during a write, reconnect with a
read-only check and verify the outcome before deciding whether to repeat it.
