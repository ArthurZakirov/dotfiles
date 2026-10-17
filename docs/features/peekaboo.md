# 🖥️ Peekaboo computer use

[← Features](README.md) · [Application provisioning](applications.md)

Both Mac profiles provision the [Peekaboo](https://github.com/openclaw/Peekaboo)
CLI with Homebrew in [`src/apps.sh`](../../src/apps.sh). The
[`run_after_40-ensure-peekaboo-skill.sh.tmpl`](../../home/run_after_40-ensure-peekaboo-skill.sh.tmpl)
hook installs the **official upstream** `peekaboo` Agent Skill for the installed
agent ecosystems:

- `~/.agents/skills/peekaboo/SKILL.md` — shared skills location (Codex / SkillPort).
- `~/.claude/skills/peekaboo` — a symlink to that same skill (Claude Code).

The hook downloads the single upstream skill file from the pinned Peekaboo
release **v4.9.5**, verifies its SHA-256 before installing, and records the
installed digest in `~/Library/Caches/chezmoi/peekaboo-skill.sha256`.
Subsequent applies do not redownload unchanged content. Upgrades must change
both the release URL and checksum in the hook. The content stays upstream;
there is no independent in-repository copy to maintain.

Existing unrelated skill directories and symlinks are not overwritten.
Unrecognized or locally edited `SKILL.md` files cause the setup to fail with a
diagnostic rather than destroying user changes. A failed download or checksum
check leaves the previously installed skill intact. The optional app/skill setup
is skipped under `DOTFILES_SKIP_OPTIONAL_APPS=1` (headless CI).

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
