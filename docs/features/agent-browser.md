# 🌐 Agent Browser automation

[← Features](README.md) · [Peekaboo computer use](peekaboo.md)

Both Mac profiles install the [Vercel agent-browser](https://github.com/vercel-labs/agent-browser)
CLI through npm in [`src/apps.sh`](../../src/apps.sh), alongside the standalone
Vercel [`skills` CLI](https://github.com/vercel-labs/skills) (the package invoked
by `npx skills`). The
[`run_after_50-ensure-agent-browser.sh.tmpl`](../../home/run_after_50-ensure-agent-browser.sh.tmpl)
hook then installs the official **global** `agent-browser` skill using the
installed `skills add` command for **Codex** and **Claude Code**.

- `~/.agents/skills/agent-browser/SKILL.md` is the canonical Vercel skill.
- `~/.claude/skills/agent-browser` points to that same installation.
- `~/.agents/.skill-lock.json` is npx skills' upstream provenance metadata.
- `~/Library/Application Support/dotfiles/agent-browser-skill.sha256` stores
  the local integrity digest of the installed canonical skill.

Installations are noninteractive and idempotent. Existing skills not recorded as
coming from `vercel-labs/agent-browser`, or subsequently edited locally, are
**not overwritten**. An existing official skill is adopted without redownloading.
Missing Claude links are repaired without reinstalling the canonical skill.
To request a new upstream skill version deliberately, use `npx skills update -g
agent-browser -y` and review the resulting file; subsequent chezmoi runs stop
on a changed digest until you reconcile the local ownership record.

The hook also runs `agent-browser install` to provision Chrome for Testing.
This is a separate browser runtime, not the Chrome profile used for personal
browsing. Subsequent runs can reuse the downloaded runtime; no browser window
is opened during installation. These optional tools are skipped in headless
provisioning with `DOTFILES_SKIP_OPTIONAL_APPS=1`.

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

The `skills` CLI is installed globally, rather than fetched implicitly on
every `npx` invocation. `npx skills` remains available and equivalent.

The installed `SKILL.md` is a **discovery stub**. The version-matched, detailed
workflow documentation remains in the CLI (`agent-browser skills get core` and
`agent-browser skills get electron`), so there is no duplicated Electron skill
to install. Prefer the browser tool for web content and CDP-compatible Electron
apps, and [Peekaboo](peekaboo.md) for native macOS UI and final visual checks.

## Test fidelity

[`tests/integration/test_computer_use_real.sh`](../../tests/integration/test_computer_use_real.sh)
provisions the real npm CLI, Vercel npx skill, Peekaboo skill, and Chromium in a
disposable HOME and performs browser click/snapshot verification. The macOS CI
job runs this separately from stubbed and profile-rendering tests. **Never run
fresh-home provisioning against an already configured Mac's real HOME.**
