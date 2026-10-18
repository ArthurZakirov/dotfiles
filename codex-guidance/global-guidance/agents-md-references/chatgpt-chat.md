# ChatGPT Chat runtime guidance

## Remote computer access

When work on Arthur's computer is needed from ordinary ChatGPT Chat, prefer the available Remote Desktop Commander connection rather than assuming local desktop access.

- Use Remote Desktop Commander for filesystem, terminal, process, and machine-level operations on the connected computer.
- Approval UI is controlled by ChatGPT's tool-authorization layer, not by the Desktop Commander MCP server itself. Desktop Commander tool history does not expose the UI-gating decision.
- If a tool invocation returns a pending approval/request state, tell Arthur that approval is required and why, then use that native pending request. Do not substitute conversational assent for it.
- Do not claim a particular Desktop Commander command, connectivity check, retry pattern, or verbal prompt will make the approval UI appear unless the current tool flow explicitly provides evidence for that behavior.
- If no pending approval state is returned, treat the reason for UI visibility or non-visibility as unknown rather than inferring a trigger from timing alone.
