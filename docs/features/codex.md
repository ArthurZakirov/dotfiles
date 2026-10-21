# Codex configuration and global guidance

[← Feature catalog](README.md)

Start with Codex instructions and hooks refined through hundreds of hours of real software-development work, without having to design and tune them all yourself.

Chezmoi installs the versioned Codex files directly from this DevMac repository.
Neither installation nor synchronization requires cloning or invoking another
repository. The global guidance source tree and its renderer are **build-time
files only**, not a second installation inside `~/.codex/`.

## Managed files

| Destination under `~/.codex/` | Repository source | Scope |
| --- | --- | --- |
| `AGENTS.md` and `agents-md-references/` | [`home/dot_codex/`](../../home/dot_codex/) | Shared across profiles; `chezmoi apply` copies the checked-in generated files. |
| `.vscode/settings.json` | [`home/dot_codex/dot_vscode/settings.json`](../../home/dot_codex/dot_vscode/settings.json) | Shared VS Code Explorer visibility settings. |
| `keybindings.json` | [`home/dot_codex/keybindings.json`](../../home/dot_codex/keybindings.json) | Shared desktop-app keyboard shortcuts (not VS Code shortcuts). |
| `config-toml/realtime-voice-backend-prompt.md` | [`home/dot_codex/config-toml/realtime-voice-backend-prompt.md`](../../home/dot_codex/config-toml/realtime-voice-backend-prompt.md) | Version-controlled Live Voice prompt source. |
| `config-toml/sync-voice-prompt.py` | [`home/dot_codex/config-toml/sync-voice-prompt.py`](../../home/dot_codex/config-toml/sync-voice-prompt.py) | Shared, pinned TOML renderer used internally by chezmoi. |
| `config.toml` (one key only) | [`home/dot_codex/modify_private_config.toml.tmpl`](../../home/dot_codex/modify_private_config.toml.tmpl) | Native chezmoi modifier: changes only the Live Voice prompt, preserving machine-local settings. |
| `hooks.json` | [`home/dot_codex/hooks.json.tmpl`](../../home/dot_codex/hooks.json.tmpl) | Shared hook registration and configuration. |
| `hooks-json/` | [`home/dot_codex/hooks-json/`](../../home/dot_codex/hooks-json/) | Shared hook scripts and supporting files. |
| `langsmith.json` | [`home/dot_codex/private_langsmith.json`](../../home/dot_codex/private_langsmith.json) | Personal profile only; installed with private (0600) permissions. |

## Editing global guidance

The canonical manifest, ordered components, references, and Python generator live
in [`src/codex-guidance/`](../../src/codex-guidance/), **outside chezmoi's `home/`
source directory**. Only the resulting `AGENTS.md` and its runtime references
are installed. To change guidance, edit the canonical source, regenerate the
checked-in results, inspect the diff, then apply:

```sh
# From the Dotfiles Git root, with project Python dependencies installed:
python3 src/codex-guidance/render.py
python3 src/codex-guidance/render.py --check
git diff -- home/dot_codex/AGENTS.md home/dot_codex/agents-md-references
chezmoi --no-pager diff "$HOME/.codex"
chezmoi apply "$HOME/.codex/AGENTS.md" "$HOME/.codex/agents-md-references"
```

For a fresh Mac or to synchronize all managed dotfiles, run `chezmoi apply`.
No dedicated guidance download script or shell alias is required. The renderer
uses an isolated temporary directory when generating results; it never installs
canonical components or auxiliary harness settings on the active machine.


## Live Voice prompt and upstream reference

The [custom Live Voice prompt](../../home/dot_codex/config-toml/realtime-voice-backend-prompt.md)
is a **complete replacement** for the built-in Codex prompt, not an
append-only supplement. In particular, it tells the voice frontend to
explicitly distinguish direct answers, backend handoffs, and backend findings.

For comparison, the [unmodified upstream prompt](../../src/codex-guidance/upstream/realtime/backend_prompt.md)
is checked in **for reference only**; chezmoi does not install it. It was
retrieved from [openai/codex at commit `8c076942`](https://github.com/openai/codex/blob/8c076942cb70fba8e5c4732c23f1faabc4aed484/codex-rs/prompts/templates/realtime/backend_prompt.md).
The upstream `{{ user_first_name }}` placeholder is intentionally preserved
there; Codex normally substitutes it at runtime. The custom prompt has its
own name value and additional workflow guidance. The
[upstream selection code](https://github.com/openai/codex/blob/8c076942cb70fba8e5c4732c23f1faabc4aed484/codex-rs/core/src/realtime_prompt.rs)
confirms that a nonempty config override replaces the built-in prompt.

Review the differences in VS Code or the terminal:

```sh
git diff --no-index -- \
  src/codex-guidance/upstream/realtime/backend_prompt.md \
  home/dot_codex/config-toml/realtime-voice-backend-prompt.md
```

The snapshot stays pinned for reproducible comparison. Refresh it deliberately
from the upstream repository when evaluating a newer Codex release; do not
silently overwrite it during `chezmoi apply`.

## Machine-local Codex state

**Codex still owns `~/.codex/config.toml`, except for
`experimental_realtime_ws_backend_prompt`.** Project trust, MCP servers,
plugin choices, model and sandbox permissions, and desktop preferences stay
machine-local and may be edited through the Codex or Desktop UI. None of those
values are copied into Dotfiles or overwritten by chezmoi.

The built-in [`modify_` source](../../home/dot_codex/modify_private_config.toml.tmpl)
passes the current `config.toml` to the
[pinned TOML renderer](../../home/dot_codex/config-toml/sync-voice-prompt.py).
That renderer updates **only the Live Voice prompt** using the
[versioned Markdown source](../../home/dot_codex/config-toml/realtime-voice-backend-prompt.md),
validates all other parsed settings are unchanged, and preserves unrelated
formatting and comments. It reads and writes through standard input/output;
chezmoi performs the actual file update with private (0600) permissions.
A first install can initialize a missing `config.toml` without `uv`; editing
an existing config requires `uv`, which is included in the [common CLI manifest](../../dependencies/brew/common/cli.Brewfile).

**The usual `chezmoi diff` now includes pending changes to the active
`config.toml`**, even when the installed Markdown file is already up to date
or the prompt was edited through the Desktop UI. The existing VS Code diff
adapter displays those changes as a readable Markdown comparison, without
caching or opening unrelated local TOML settings.

`chezmoi apply` updates the prompt only if Codex and ChatGPT Desktop are not
running. Otherwise, the modifier leaves the active config unchanged and
reports that the update was deferred; `chezmoi diff` continues showing the
pending change. Close the apps and run `chezmoi apply` again. No full-file
template, automatic reverse synchronization, or project-trust replication is
introduced.

Skills are managed by `npx skills`, not chezmoi. Authentication, sessions,
plugin installations, databases, cache, backups, and temporary data remain
excluded via [`home/.chezmoiignore`](../../home/.chezmoiignore) and
[repository Git ignores](../../.gitignore). Existing unmanaged runtime
directories are **not deleted automatically**; review them separately after
the new guidance is applied successfully.
