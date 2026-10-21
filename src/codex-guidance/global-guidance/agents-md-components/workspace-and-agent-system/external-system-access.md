<a id="external-system-access"></a>
# 🔌 External system access

Prefer structured, authenticated integrations over UI automation for account-backed systems. Use browser interaction as a fallback, not as the default access path.

| When | Then |
| --- | --- |
| A task requires reading from, writing to, or operating an account-backed external system such as GitHub, Jira, Notion, Gmail, Bitbucket, Databricks, or another authenticated service. | Before using browser automation, inspect the capabilities already available in the current runtime: native connectors, plugins, MCP tools, APIs, and installed or official CLIs. Prefer the narrowest structured interface that directly supports the task. |
| No suitable structured integration is currently available or connected. | Check whether an appropriate plugin, MCP integration, API path, or official CLI is discoverable and practical to use. If connection, setup, or authentication is the only blocker, ask the user to connect or authenticate through the supported flow rather than immediately falling back to browser automation. Do not install software, change credentials, or broaden permissions without the authorization required for that action. |
| A structured integration is unavailable, cannot perform the required operation, or remains blocked after the supported connection/authentication path is attempted or declined. | Use browser interaction as the fallback. When the runtime can control the user's regular Chrome profile and the task benefits from existing sessions, extensions, or password-manager access, prefer that Chrome profile over an isolated or in-app browser; otherwise use the available browser surface and state the limitation when it materially affects the task. |
| The task is ordinary public-web research that does not require the user's account, private data, or an authenticated action. | Use the most appropriate research/browser tooling directly; do not add integration-discovery or authentication work that does not help the task. |
