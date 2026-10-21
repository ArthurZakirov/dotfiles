# 🌐 Agent Browser automation

[← Features](README.md) · [Peekaboo computer use](peekaboo.md)

Both Mac profiles install the [Vercel agent-browser](https://github.com/vercel-labs/agent-browser)
CLI through npm in [`src/apps.sh`](../../src/apps.sh), alongside the standalone
Vercel [`skills` CLI](https://github.com/vercel-labs/skills) (the package invoked
by `npx skills`). The
[`run_after_50-ensure-agent-browser.sh.tmpl`](../../home/run_after_50-ensure-agent-browser.sh.tmpl)
hook installs the official global `agent-browser` skill using
`npx --no-install skills add` for **Codex only**.

- `~/.agents/skills/agent-browser/SKILL.md` is the installed Vercel skill.
- `~/.agents/.skill-lock.json` is the upstream provenance metadata.
- `~/Library/Application Support/dotfiles/agent-browser-skill.sha256` stores
  the local integrity digest of the installed canonical skill.

Installation is noninteractive and idempotent through the shared
[`src/agent-skills.sh`](../../src/agent-skills.sh). Skills with unrelated
provenance or locally changed contents are **not overwritten**. An existing
official skill is reused without redownloading it.
To update the upstream skill deliberately, run `npx --no-install skills update -g agent-browser -y`
and review the new `SKILL.md`. Since its digest has changed, subsequent applies
will refuse to adopt it until you explicitly remove the old marker:

```sh
rm "$HOME/Library/Application Support/dotfiles/agent-browser-skill.sha256"
```

The next `chezmoi apply` verifies the upstream provenance recorded by Vercel's
`skills` installer before accepting the updated file and storing its digest.
Do not remove the marker to suppress an unknown or unreviewed local change.

The hook checks for an existing working Chrome for Testing, system Chrome, or
compatible Chromium executable **before** downloading anything. Existing browser
runtimes remain in place: a normal chezmoi apply does not implicitly upgrade
Chrome for Testing. A separate explicit update is required to do that.
When no browser executable is available, the helper runs agent-browser install.
The optional hook is skipped by DOTFILES_SKIP_OPTIONAL_APPS=1.

## Verify

```sh
agent-browser --version
agent-browser skills get core
agent-browser skills get electron   # VS Code and other Electron apps
skills --version
skills list -g
agent-browser open 'data:text/html,<h1>ready</h1>'
agent-browser snapshot
agent-browser close
```

The `skills` CLI is installed globally, and the setup uses `npx --no-install`
to invoke that managed version without fetching a separate copy.

The installed `SKILL.md` is a **discovery stub**. The version-matched, detailed
workflow documentation remains in the CLI (`agent-browser skills get core` and
`agent-browser skills get electron`), so there is no duplicated Electron skill
to install. Prefer the browser tool for web content and CDP-compatible Electron
apps, and [Peekaboo](peekaboo.md) for native macOS UI and final visual checks.

## Test fidelity

[`tests/integration/test_computer_use_real.sh`](../../tests/integration/test_computer_use_real.sh)
provisions the real npm CLIs, both official npx skills, and Chromium in a
disposable HOME and performs browser click/snapshot verification. The macOS CI
job runs this separately from stubbed and profile-rendering tests. **Never run
fresh-home provisioning against an already configured Mac's real HOME.**
