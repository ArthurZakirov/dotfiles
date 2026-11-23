# 🌐 Use your signed-in Chrome

Both Mac profiles install the [Browser Use CLI](https://github.com/browser-use/browser-use)
with `uv` during `chezmoi apply`. Codex uses the managed copy in
`~/.local/share/dotfiles/browser-use/bin/`. A fresh install also creates
`~/.local/bin/browser-use`; an existing executable at that path is preserved. Ask Codex to open a page in your browser. For signed-in work it runs
`browser-use-signed-in`, which checks the existing connection before reading
Chrome’s discovery file.
If Chrome requests remote debugging, review the prompt. The local workflow
uses the running browser across commands. Chrome can request approval again
after a disconnect or restart.

## When Chrome asks for your help

An interactive `chezmoi apply` prepares the connection while you are at the
keyboard. If Chrome needs its debugging setting enabled, setup opens that page
and names the checkbox. Unattended installs defer the connection until use.

Codex can open regular Chrome and try an already authorized way to operate its
window. If Chrome shows **Allow remote debugging?**, review that prompt. If the
browser setting is off, Codex can open the relevant Chrome page for you.
An “Operation not permitted” file error can also come from the calling app or
its sandbox. It alone does not identify a missing Chrome or macOS setting.

## Restore the previous setup

The [previous routing rule](../../archive/agent-chrome/routing.md) and
[recovery procedure](../../archive/agent-chrome/signed-in-chrome-fallback.md)
are archived with the original implementation. Revert the Browser Use migration
in a Dotfiles branch and apply the reviewed result to restore the previous
default. The previous installer can recreate its official skill. Custom skill
contents moved during migration are preserved under
`~/Library/Application Support/dotfiles/retired-skills/`.
