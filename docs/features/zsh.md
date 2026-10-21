# 🐚 Zsh configuration

[← Features](README.md) · [How it works](../architecture.md)

Both profiles share the same shell prompt, persistent history, completion,
fzf search, Git helpers, suggestions, and syntax highlighting. The personal
profile also loads its optional integrations.

## 🧰 Installation and managed files

The [setup workflow](../setup.md) installs dependencies before applying the
managed shell configuration. Open a new Terminal after applying changes.
An existing `.zshrc` is backed up before its first replacement.

| Source | Responsibility |
| --- | --- |
| [Zsh template](../../home/dot_zshrc.tmpl) | Shared shell behavior and commands |
| [Personal template](../../home/.chezmoitemplates/personal.zsh) | Personal-only environment and integrations |
| [Git dependency manifest](../../dependencies/git/common/oh-my-zsh.commit) | Pinned Oh My Zsh revision |
| [Brewfile](../../dependencies/brew/required.Brewfile) | Shell dependencies |

Keep machine-local additions in `~/.zshrc.local`, which the shared shell sources
when present. This file is unmanaged and remains on that machine. To share a
shell change across Macs, edit the templates using the
[development workflow](../development.md#step-3--edit-or-add-dotfiles).
