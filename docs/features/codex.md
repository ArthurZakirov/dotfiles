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
git diff -- home/dot_codex/AGENTS.md.tmpl home/dot_codex/agents-md-references
chezmoi --no-pager diff "$HOME/.codex"
chezmoi apply "$HOME/.codex/AGENTS.md" "$HOME/.codex/agents-md-references"
```

For a fresh Mac or to synchronize all managed dotfiles, run `chezmoi apply`.
No dedicated guidance download script or shell alias is required. The renderer
uses an isolated temporary directory when generating results; it never installs
canonical components or auxiliary harness settings on the active machine.


## Live Voice prompt and upstream reference

The [custom Live Voice prompt](../../home/dot_codex/config-toml/realtime-voice-backend-prompt.md)
replaces the built-in Codex prompt to make spoken code exploration, understanding,
and review easier. It helps keep the conversation connected to the relevant code
in the editor, reducing the effort needed to follow an explanation.

The realtime voice frontend and the backend agent have different visibility
into repository context, instructions, and execution tools. The custom
configuration bridges that gap for a more coherent workflow. The detailed
interaction rules live in the versioned voice prompt and the relevant
[global agent guidance](../../src/codex-guidance/global-guidance/), rather
than being duplicated in this feature guide. This override applies to
**Codex Live Voice**, not to ordinary ChatGPT Voice.

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

`chezmoi apply` writes the versioned prompt to `config.toml` even while
Codex CLI, Codex Desktop, or ChatGPT Desktop is running. The modifier does not
inspect or terminate running application processes. `chezmoi diff` shows a
pending change before applying it and becomes clean afterward. An existing
voice call or app session may continue using previously loaded instructions;
restart the voice call or app later if the new prompt is not picked up. Updating
the file does not guarantee hot-reloading in existing sessions. No full-file
template, automatic reverse synchronization, or project-trust replication is
introduced.

Skills are managed by `npx skills`, not chezmoi. Authentication, sessions,
plugin installations, databases, cache, backups, and temporary data remain
excluded via [`home/.chezmoiignore`](../../home/.chezmoiignore) and
[repository Git ignores](../../.gitignore). Existing unmanaged runtime
directories are **not deleted automatically**; review them separately after
the new guidance is applied successfully.

## On-demand AGENTS.md freshness check

Use the managed [`agents-freshness` custom prompt](../../home/dot_codex/prompts/agents-freshness.md)
from a local Codex conversation:

```text
/prompts:agents-freshness
```

The prompt asks Codex to run the existing read-only freshness checker using
`CODEX_THREAD_ID`, which identifies the conversation executing the shell
tool. The reply is always **current**, **outdated**, or **unverifiable**,
rather than interpreting no automatic hook notification as success.
No Hammerspoon keyboard shortcut, window-focus detection, or session picker is
required. The agent performs a read-only shell call only when you invoke the
prompt; the normal automatic hooks remain independent.

Custom prompts currently work in Codex CLI, the Codex IDE extension, and the
ChatGPT desktop Codex composer, but are **deprecated** in favor of Agent
Skills. Their invocation or discovery may change in future releases.
Restart the relevant app or open a new chat after installing the prompt so it
appears in the slash-command menu.

The checker is distributed separately by the
[AGENTS.md freshness hook feature](https://github.com/ArthurZakirov/dotfiles/pull/38);
install that feature first if it has not yet been merged. When a chat cannot
execute a local shell command or `CODEX_THREAD_ID` is unavailable, the status
is **unverifiable**, never falsely green. Actual delivery of the expanded
prompt and the model's use of the tool are surface-specific and should be
confirmed in the interactive app.

## Desktop AGENTS.md check without an agent turn

With a local Codex chat open in **ChatGPT desktop / Codex desktop**, press
**Control–Option–Command–F**. The chezmoi-managed
[Hammerspoon module](../../home/dot_hammerspoon/modules/agents_freshness.lua)
triggers the native **Copy chat deep link** action (Command–Option–L),
extracts that conversation's technical thread ID, and calls the local
read-only [freshness checker](https://github.com/ArthurZakirov/dotfiles/pull/38)
with `--check --session-id`. This works while the agent is busy:
no Codex prompt, model invocation, message, or thread interruption.

The temporary status card appears **only after the check completes** and
reports **current**, **outdated**, or **not verified**. It stays visible for
about 1.4 seconds when current, or 2 seconds for the other results. The last status is used for a missing link, unsupported
app, absent checker, or missing model-visible snapshot. The action handles
only local Codex threads; an ordinary ChatGPT conversation is not a local
Codex transcript and cannot be verified by this checker.

The shortcut leaves the app in focus. It backs up and restores the first
clipboard item, including supported rich formats, and refuses to overwrite
multi-item clipboard contents. If the clipboard changes to something other
than a Codex link, the action leaves the new content untouched. No new
daemon or always-on polling is installed.

The target Mac has `/Applications/ChatGPT.app` with the
`com.openai.codex` bundle ID; the Codex interface is part of that desktop
app. Actual keyboard behavior depends on the app's shortcut assignment
remaining **Copy chat deep link → Command–Option–L**.
