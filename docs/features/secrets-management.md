# Shared secrets management (personal Mac)

[← Features](README.md) · [Setup](../setup.md)

Credentials are handled by the **shared dotfiles infrastructure**, not by any
one feature. The reusable Python module
`~/.local/share/dotfiles-secrets/secret_store.py` exposes
`read_secrets(names, account, inherited)` to any integration that needs an
API key at runtime.

The module reads the configured service credential from macOS Keychain,
retrieves values from the configured secret backend, and returns **only the
requested names**. It never prints credential values. Errors are redacted.
Child services receive only the specific credentials required by their
runtime, not the general secret-manager credential.

The personal shell profile already uses the same Keychain account and its
shared secret loader for interactive processes. The Python helper supports
noninteractive launchd services without duplicating backend-specific logic.
Keep secret values, runtime tokens and machine-specific credentials out of Git,
LaunchAgent plists, shell command lines and documentation.

## Provisioning

The secret backend and its Keychain access are configured **once per personal
Mac** as part of the common dotfiles environment. Integrations only declare
which secret names they need; they must not duplicate backend setup instructions.

Some external accounts and resources cannot be created solely by applying
dotfiles. For those prerequisites, use the provider's authenticated setup UI
or existing account provisioning. After they exist, `chezmoi apply` installs
and maintains compatible local services without feature-specific terminal
commands.

Professional profile deployments do not install this personal-only helper.
