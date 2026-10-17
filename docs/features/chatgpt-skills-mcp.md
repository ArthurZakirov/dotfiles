# ChatGPT local Agent Skills (personal Mac)

[← Features](README.md) · [Setup](../setup.md)

## What this does

Normal **ChatGPT Chat** can call a custom MCP plugin whose three stable tools
search and read the installed Agent Skills. The bridge does not install, edit
or synchronize skills; SkillPort owns `~/.agents/skills` (including its
symlinks) and the canonical Git repositories remain unchanged.

```text
Installed ~/.agents/skills/
  -> FastMCP server (stdio, read-only)
  -> OpenAI tunnel-client
  -> Secure MCP Tunnel
  -> Custom MCP plugin -> normal ChatGPT Chat
```

The tools `search_skills(query, limit, offset)`, `read_skill(name)`, and
`read_skill_resource(name, path)` load fresh local files for each call.
They do not require a new plugin upload after a `SKILL.md` or reference edit.
The MCP tool descriptions *encourage* ChatGPT to search on relevant requests;
**automatic invocation is model-mediated, not guaranteed**. A new plugin install
and first ChatGPT-chat discovery are still required on each account/workspace.

## Install and configure on each personal Mac

1. Apply your updated dotfiles following [the safe chezmoi setup](../setup.md).
   The personal app installer installs the official
   `brew install openai/tools/tunnel-client`; the shared Brewfile already
   provides `uv`. The service's frozen Python dependencies are installed by
   `uv sync` at first configured apply. Professional machines skip the plugin.
2. In [OpenAI Platform Tunnels](https://platform.openai.com/settings/organization/tunnels),
   create or choose a tunnel attached to the ChatGPT workspace. Do not reuse
   an ID simultaneously from two Macs. The owner of the runtime credential must
   have Tunnels **Read + Use**.
3. Put a restricted runtime API key in **Bitwarden Secrets Manager** as the
   secret named `OPENAI_TUNNEL_API_KEY`. The existing `BWS_ACCESS_TOKEN`
   is held in macOS Keychain under the account chosen in chezmoi's personal
   profile setup (`bwsAccount`). No secret value belongs in Git, a plist,
   `~/.zshrc.local`, or a tunnel-client profile.
4. After reviewing the tunnel ID, run (only once per Mac):

   ```sh
   skillport-mcp-configure tunnel_YOUR_ID_FROM_PLATFORM
   ```

   This creates `~/.config/skillport-mcp/tunnel-id` (mode 0600) and refuses
   to replace an existing file. The ID is machine-local and not tracked.
5. **Stop any existing foreground demo `tunnel-client run` for that ID**
   before proceeding. Stdio tunnels cannot have multiple active runtimes
   on the same tunnel. With the personal files applied, run `chezmoi apply`
   after configuration to synchronize the Python environment and register
   `com.arthur.skillport-mcp` under user launchd. Setup exits without starting
   a service if no tunnel ID exists. It refuses to take over an unmanaged
   existing service with the same label.
6. Inspect the service:

   ```sh
   launchctl print "gui/$(id -u)/com.arthur.skillport-mcp"
   tail -n 30 "$HOME/Library/Logs/skillport-mcp.err.log"
   ```

   The launcher retrieves the Bitwarden access token from Keychain and
   injects only `CONTROL_PLANE_API_KEY` into the tunnel process; the MCP child
   explicitly unsets credential variables before running. There is no
   shell-history/API-key echo step.
7. In ChatGPT **Plugins → Add custom MCP server**, select **Tunnel**,
   choose the existing tunnel ID, select authentication **None** for this
   read-only server, and create the plugin. In a new **normal Chat** (not Work),
   request `search_skills` and `read_skill`. Existing demo plugin tool catalogs
   may require a manual refresh/reconnection when switching from the stub
   to the real server; subsequent content changes require no reinstallation.

## Operations and boundaries

- Server source: `~/.local/share/skillport-mcp/server.py`. Python environment
  at `~/.local/share/skillport-mcp/.venv`; only the package declarations and
  lockfile are managed by chezmoi. The environment is generated locally.
- Installed skill directory: `~/.agents/skills`. Override with
  `SKILLPORT_SKILLS_ROOT` only when testing or with an explicitly trusted
  directory. Canonical top-level skill symlinks are supported.
- Safety: only declared text-like resources within a selected skill are read,
  with 256 KB per-file limit; `..`, hidden resource paths and escaping
  resource symlinks are rejected. A top-level skill symlink is explicitly trusted
  and may resolve to its canonical repository outside the skill root.
- Keep this Mac awake and logged in for live access. The tunnel-client
  must run for discovery and tool calls. An outgoing tunnel does not grant
  ChatGPT arbitrary filesystem access, but **skill instructions and read
  references are transmitted to ChatGPT** when tools are invoked; do not include
  private data in accessible skill contents.
- A change to MCP tool schemas or server behavior may need a restart and a
  ChatGPT plugin refresh. A change to a skill's content does not.
- If switching the Mac to `professional`, the chezmoi after-hook stops/removes
  only a service previously proven managed by its marker; unrelated services
  are left alone. Local tunnel configuration is retained until removed manually.
- Don't use `nohup`/`disown` to keep a second daemon alive. Managed
  launchd handles login startup and restarts, with throttling to avoid rapid
  Keychain failures. On credential failure, inspect the redacted startup error
  and check the Keychain grant / Secrets Manager entry.

Official references: [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels),
[tunnel-client setup](https://github.com/openai/tunnel-client/blob/v0.0.16/README.md),
[FastMCP](https://gofastmcp.com/).
