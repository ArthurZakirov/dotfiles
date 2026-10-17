# Secrets management (personal Mac)

[← Features](README.md)

Bitwarden Secrets Manager stores API keys for independent dotfiles features.
The shared [credential helper](../../home/dot_local/share/dotfiles-secrets/secret_store.py)
reads only the requested secrets. No values or Mac-specific access tokens
belong in Git.

The linked Bitwarden help pages are the **current source for UI navigation**;
menu names below may change.

## One-time organization and project setup

Skip resources that already exist.

1. In the [Bitwarden web vault](https://vault.bitwarden.com/), open
   **Secrets Manager**. If unavailable, follow the
   [organization setup instructions](https://bitwarden.com/help/secrets-manager-quick-start/)
   to enable it and grant the relevant person access.
2. Select **New → Project**, name the project and **Save**. A secret belongs
   to exactly one project.
3. Open the project → **People**, choose the members/groups who may manage
   its secrets, select **Add**, and assign **Can read** or **Can read, write**
   as appropriate.

[Bitwarden organization setup](https://bitwarden.com/help/secrets-manager-quick-start/) ·
[Project access](https://bitwarden.com/help/projects/)

## Grant machine access

Repeat for each machine account; reuse an existing suitable project/account
rather than creating duplicates.

1. Select **New → Machine account**, name it and **Save**.
2. Open the machine account → **Projects**, select the project, **Add** and
   grant **Can read** for runtime secret retrieval.
3. Under **People**, select **Add** for any person who must be permitted to
   manage the machine account and issue its tokens.
4. Open **Access tokens → Create access token**, enter a name and expiration,
   and create the token. **Copy it now**: Bitwarden does not show it again.

Machine accounts access **projects/secrets**; an individual Mac uses the
machine account's access token. The project/secret grants are what determine
which values it can read—not a generic "enable this Mac" checkbox.

[Machine accounts and project permissions](https://bitwarden.com/help/machine-accounts/) ·
[Access tokens](https://bitwarden.com/help/access-tokens/)

## Add a secret to the vault

Repeat for each new API key, using the secret name required by its feature.

1. In **Secrets Manager**, select **New → Secret**.
2. Enter its **Name** (for example, the feature's expected environment
   variable) and paste the value into **Value**.
3. Under **Project**, select the project that will contain the secret.
4. Open the **Machine accounts** tab and select the machine account(s) that
   should receive **direct access to this secret**. Use the **People** tab
   separately if individual members also need direct access.
5. Select **Save**.

Machine accounts with **Can read** access to the selected project can already
retrieve its secrets; an additional direct assignment is not required for
those accounts. Use the **Machine accounts** tab when assigning access to the
specific secret rather than the entire project.

[Bitwarden secret creation and direct permissions](https://bitwarden.com/help/secrets/)

## Authorize a new Mac

1. Open **Keychain Access** on that Mac and create a new password item
   (**⌘N**).
2. Set **Name** to `BWS_ACCESS_TOKEN` (the service name expected by the
   [shared credential helper](../../home/dot_local/share/dotfiles-secrets/secret_store.py)),
   **Account** to the account configured in the
   [personal chezmoi template](../../home/.chezmoi.toml.tmpl), and **Password**
   to the token created under [Grant machine access](#grant-machine-access).
   Save the item in the user's login keychain.
3. Approve macOS's Keychain access request for the configured application
   when it first retrieves the credential.

The [shared credential helper](../../home/dot_local/share/dotfiles-secrets/secret_store.py)
reads the Keychain entry at runtime; integrations do not duplicate this
backend logic. No feature-specific shell exports or service commands are needed.

[Bitwarden's Keychain setup](https://bitwarden.com/blog/how-to-securely-store-your-secrets-manager-access-tokens-with-bash-scripting/) ·
[macOS Keychain permissions](https://support.apple.com/guide/keychain-access/kyca1243/mac)
