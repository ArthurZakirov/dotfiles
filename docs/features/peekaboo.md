# 🖥️ Peekaboo computer use

[← Features](README.md) · [Application provisioning](../provisioning.md)

Both Mac profiles provision the [Peekaboo](https://github.com/openclaw/Peekaboo)
CLI with Homebrew in [`src/apps.sh`](../../src/apps.sh). The
[`run_after_40-ensure-peekaboo-skill.sh.tmpl`](../../home/run_after_40-ensure-peekaboo-skill.sh.tmpl)
hook installs the official `peekaboo` skill using `npx --no-install skills add`
for **Codex only**, in `~/.agents/skills/peekaboo/SKILL.md`. The shared
[`src/agent-skills.sh`](../../src/agent-skills.sh) uses the globally managed
`skills` npm package. Upstream provenance is recorded in
`~/.agents/.skill-lock.json`, while the installed content digest is tracked in
`~/Library/Application Support/dotfiles/peekaboo-skill.sha256`.

Existing skill directories without matching upstream provenance, or skills
changed since the previous apply, are not overwritten. After deliberately
updating the skill with `npx --no-install skills update -g peekaboo -y`, inspect
its contents; only then remove the digest marker to allow the next `apply` to
adopt the change. Skills are not copied into the repository and no other
agent's skill location is touched. The optional install is skipped under
`DOTFILES_SKIP_OPTIONAL_APPS=1` for headless CI.

## macOS permissions and verification

Homebrew installation does **not** grant macOS Screen Recording, Accessibility,
or event-injection permissions. Inspect the permissions for the actual execution
host and approve missing permissions manually under System Settings → Privacy &
Security. They are not portable between Macs and cannot be provisioned by
chezmoi.

```sh
peekaboo --version
peekaboo permissions status
peekaboo app list --json
peekaboo see --app Code --no-elements --path /tmp/peekaboo-vscode.png --json
```

For screenshot-based verification, an agent must also be able to **read the
captured image**; successful capture or input dispatch alone does not prove
the UI behaves as intended. Structured AX element inspection may fail for some
Electron windows even with granted permissions; use the official skill's
documented fallbacks and independently verify the visible outcome.

Develop in a separate worktree only with explicit `chezmoi --source
<worktree>/home` arguments for isolated tests. Normal `chezmoi apply`
continues to operate on the configured primary checkout; do not use it to test
an unmerged worktree on an active Mac.
