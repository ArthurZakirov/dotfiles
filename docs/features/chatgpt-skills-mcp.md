# Local Agent Skills in ChatGPT

[← Features](README.md)

ChatGPT can discover and read the Agent Skills installed in `~/.agents/skills/`.
The MCP bridge is read-only and **personal-profile only**. Skill installation
and synchronization are independent of this feature.

## First-time setup

Complete these steps for a new OpenAI account or workspace. For a second Mac,
reuse existing account-side resources where appropriate, but use a separate
tunnel if both Macs will be connected simultaneously.

### 1. Create an OpenAI tunnel and runtime key

1. Open [Platform → Tunnels](https://platform.openai.com/settings/organization/tunnels)
   in the **intended Platform organization**. Create a tunnel or select an
   existing one; associate it with both the organization and the **ChatGPT
   workspace** that will use the plugin. Save its `tunnel_id`.
2. Open the organization's project **API keys** settings and select
   **Create new secret key**. Create a dedicated runtime key with **Restricted**
   permissions; grant only the access needed for the tunnel. Copy the key
   securely when it is displayed.
3. Confirm the Platform organization has granted **Tunnels Read + Use** to
   the runtime operator. Creating or editing tunnels additionally requires
   **Tunnels Read + Manage**. These organization-level permissions are
   distinct from an API key's endpoint permissions.

[OpenAI tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) ·
[API key permissions](https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform)

### 2. Provision the credentials

Use [shared secrets management](secrets-management.md#add-a-secret-to-the-vault)
to store the following **in the appropriate accessible project**:

| Secret name | Value |
| --- | --- |
| `OPENAI_TUNNEL_API_KEY` | Restricted OpenAI runtime key from step 1 |
| `OPENAI_TUNNEL_ID` (optional) | Tunnel ID, when no machine-local tunnel configuration exists |

Do not paste secret values into the repository, chat, or terminal. The common
secrets setup handles project access and the Mac's Keychain credential.

### 3. Connect the plugin in ChatGPT

1. Open [ChatGPT → Plugins](https://chatgpt.com/) in the target workspace.
2. Select **+ → Add custom MCP server**.
3. Enter a name (e.g. **Local Agent Skills**) and optional description.
4. Under **Connection**, select **Tunnel** and choose the tunnel from step 1
   (or enter its `tunnel_id`).
5. Choose **Authentication: None** for this read-only local server.
6. Check **I understand and want to continue**, then select
   **Create as a plugin**. Inspect the discovered tools.
7. In a **new normal chat**, select the plugin and ask it to call
   `search_skills` and `read_skill`. Verify that a real installed
   `SKILL.md` is returned.

[Official ChatGPT connection instructions](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)

## What dotfiles does automatically

Once the account-side tunnel and shared credentials exist, the personal
chezmoi setup installs and maintains the FastMCP server, tunnel client and
`local.skills.mcp` LaunchAgent. It starts at login and restarts on failure;
an unchanged re-apply does not restart it. Missing external credentials cause
a safe no-op. **No feature-specific terminal commands are needed.**

## Boundaries

- The professional profile does not install this bridge.
- Each call reads current files from `~/.agents/skills/`; no skill repository
  or installer is required. Reading references is limited to a selected
  skill's `references/` directory.
- Skill contents sent through the MCP tools are transmitted to ChatGPT;
  don't place private credentials inside exposed skills.
- A changed `SKILL.md` needs no plugin refresh; changed MCP tool definitions
  may require refreshing the plugin in ChatGPT.
- The Mac must be running with the user logged in for its LaunchAgent to
  serve requests.
