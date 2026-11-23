# 🌐 Use your signed-in Chrome

Both Mac profiles install the [Browser Use CLI](https://github.com/browser-use/browser-use)
with `uv` during `chezmoi apply`. Codex uses the managed copy in
`~/.local/share/dotfiles/browser-use/bin/`. A fresh install also creates
`~/.local/bin/browser-use`; an existing executable at that path is preserved. Ask Codex to open a page in your browser.
If Chrome requests remote debugging, review the prompt. The local workflow
uses the running browser across commands. Chrome can request approval again
after a disconnect or restart.

## Restore the previous setup

The [previous routing rule](../../archive/agent-chrome/routing.md) and
[recovery procedure](../../archive/agent-chrome/signed-in-chrome-fallback.md)
are archived with the original implementation. Revert the Browser Use migration
in a Dotfiles branch and apply the reviewed result to restore the previous
default. The previous installer can recreate its official skill. Custom skill
contents moved during migration are preserved under
`~/Library/Application Support/dotfiles/retired-skills/`.
