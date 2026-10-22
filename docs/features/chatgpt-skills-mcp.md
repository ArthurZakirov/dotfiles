# Local Agent Skills in ChatGPT

[← Features](README.md)

ChatGPT can search and read installed Agent Skills using a read-only MCP bridge.
The personal-profile integration does not manage the skill directory.

## First-time setup

Use the linked provider documentation as the **current source for UI navigation**.
Button names and settings pages may change; the steps below describe the
required actions, not a frozen UI.

### 1. Create a tunnel and save its ID

1. Open [OpenAI Platform → Tunnels](https://platform.openai.com/settings/organization/tunnels)
   and create or select a tunnel. Include the Platform organization and
   ChatGPT workspace that should use it.
2. Copy its **Tunnel ID** from the tunnel settings (it starts with
   `tunnel_`; it is not the display name).
3. In Bitwarden, [create a secret](secrets-management.md#add-a-secret-to-the-vault)
   with **Name:** `OPENAI_TUNNEL_ID` and **Value:** that Tunnel ID.

### 2. Create and save the runtime API key

1. Open [OpenAI Platform → Runtime API keys](https://platform.openai.com/settings/organization/api-keys)
   for the same organization. Create a **Restricted** key with only the
   required tunnel runtime permissions (**Read + Use**). The key's principal
   must also have those tunnel permissions.
2. In Bitwarden, [create another secret](secrets-management.md#add-a-secret-to-the-vault)
   with **Name:** `OPENAI_TUNNEL_API_KEY` and **Value:** the copied
   API **key**, not the Tunnel ID.

The [Bitwarden machine account](secrets-management.md#grant-machine-access)
used on this Mac must be able to read both secrets. Creating or editing a
tunnel requires different permissions (**Read + Manage**); the running
service must not use an admin key.

[OpenAI tunnel setup](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) ·
[Permissions and key types](https://github.com/openai/tunnel-client/blob/master/docs/permissions.md)

### 3. Connect the tunnel in ChatGPT

Follow the [current ChatGPT connection instructions](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt):

1. Open **Plugins → + → Add custom MCP server** in the intended workspace.
2. Enter a plugin name and optional description.
3. Choose **Connection: Tunnel** and select the tunnel created in step 1
   (or enter its Tunnel ID).
4. Choose **Authentication: None** for this read-only server, acknowledge
   the risk notice, then select **Create as a plugin**.
5. Install the newly created plugin in the intended ChatGPT workspace.
6. Open a new normal chat and select the installed plugin using `@` if it is
   not already exposed to that chat. Selection may be needed again on later
   messages. Test `search_skills` and `read_skill` against an installed skill.

Custom Instructions cannot activate an unavailable plugin. If the MCP tools are
not exposed, the [personalization guidance](chatgpt-personalization.md) uses
the local CLI fallback when Remote Desktop Commander is connected.

## Automated setup and behavior

The personal-profile dotfiles setup installs the MCP runtime and the
[LaunchAgent](../../home/private_Library/private_LaunchAgents/local.skills.mcp.plist.tmpl);
the [after-apply hook](../../home/run_after_25-ensure-local-skills-mcp.sh.tmpl)
keeps it running after login without feature-specific terminal commands.

The [launcher](../../home/dot_local/share/local-skills-mcp/launch.py) is the
source of truth for the secret names and tunnel-ID selection. On an existing
Mac, an older machine-local tunnel configuration may take precedence over
`OPENAI_TUNNEL_ID`; for a new Mac, the Bitwarden secret avoids manually
configuring an ID. The runtime key is retrieved through the
[shared secret provider](../../home/dot_local/share/dotfiles-secrets/secret_store.py).

The [MCP server](../../home/dot_local/share/local-skills-mcp/server.py)
reads installed skills at request time, independently of their installer.
It can read a selected skill's allowed references; skill content requested
by ChatGPT leaves the Mac. The professional profile does not install
this integration. The Mac must be on and logged in for the tunnel to work.

The [documentation contract tests](../../tests/unit/test_feature_documentation.py)
check the documented secret names and local links against their sources in CI.
Changes to the external OpenAI or ChatGPT UI must be checked against the
linked official instructions; they cannot be verified by local tests.
