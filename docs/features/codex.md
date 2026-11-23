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

The [AGENTS.md checker](../../home/dot_codex/hooks-json/agents-md-freshness/executable_check.py)
is installed directly by chezmoi. Automatic hook integration is maintained
separately in [PR #38](https://github.com/ArthurZakirov/dotfiles/pull/38). When a chat cannot
execute a local shell command or `CODEX_THREAD_ID` is unavailable, the status
is **unverifiable**, never falsely green. Actual delivery of the expanded
prompt and the model's use of the tool are surface-specific and should be
confirmed in the interactive app.

## AGENTS.md sync pipeline — desktop shortcut

With a local Codex chat open in **ChatGPT / Codex desktop**, press
**Control–Option–Command–F**. The managed
[Hammerspoon module](../../home/dot_hammerspoon/modules/agents_freshness.lua)
uses the native **Copy chat deep link** action (Command–Option–L) to obtain
the *visible* Codex thread ID. It launches the read-only
[pipeline checker](../../home/dot_hammerspoon/bin/executable_agents_md_pipeline)
in a separate local Python process; **no agent turn or task interruption**.

The card shows three comparisons. Each can be current, outdated, or unknown.

| Stage | What it compares |
| --- | --- |
| **Git pulled** | The checked-out guidance template and the same file at the live remote `main` commit. If that commit is unavailable locally, Git reads it in a temporary shallow clone. |
| **Chezmoi applied** | The rendered chezmoi template and the installed `~/.codex/AGENTS.md`. |
| **Session loaded** | The installed file and the global guidance recorded for the visible Codex session. |

The final card appears only once all checks complete (no intermediate blue
flashing). It closes after about three seconds if all stages match, or
four seconds when outdated/unverifiable. The app stays focused; the
shortcut preserves supported clipboard formats when the native deep link is
copied and avoids overwriting unrelated clipboard changes.

This first version supports local Codex chats in the desktop application
(bundle ID `com.openai.codex`), not terminal Codex sessions or unrelated
ChatGPT conversations.

## Resume Desktop session in Warp

With the intended Codex conversation open in the desktop app, press
**Control–Option–Command–W** (`Hyper+W`). The
[Hammerspoon hotkey](../../home/dot_hammerspoon/modules/codex_resume.lua)
reuses the [existing desktop-session capture module](../../home/dot_hammerspoon/modules/codex_desktop_session.lua):
it invokes Codex's native **Option–Command–L** Copy Link command,
extracts the exact `codex://threads/<UUID>` ID, and restores the user's
original single-item clipboard when the link is successfully copied.

The [Warp launcher](../../home/dot_hammerspoon/bin/executable_codex_resume_warp)
checks that the UUID exists in `~/.codex/state_5.sqlite` and that its
original working directory still exists. It writes a private, unique
`~/.warp/tab_configs/codex_desktop_resume_*.toml` and dispatches
`warp://tab_config/<name>`; Warp opens a new tab in its existing window.
Warp launches a short-lived wrapper from the original working directory.
It first acknowledges that the new tab's startup command is running.
**Only after that acknowledgment**, Hammerspoon gracefully quits the exact
Codex/ChatGPT Desktop app instance from which the session was copied
(`hs.application:kill()`, not a synthetic Command-Q keystroke). The wrapper
waits for the per-session writer lock in `~/.codex/thread-writer-locks/`
to be released, then replaces itself with `codex resume <UUID>`.
No manual `R` retry should be necessary in the normal case.

**Intentional side effect:** the entire Desktop app closes, including
any other open chats. Other Warp tabs remain open. Reopening Desktop
later does not deliberately take the CLI's lock back. The operation
does **not** search for other sessions by Git branch/PR, edit the Desktop
conversation, or create a new Codex session.

If the app isn't a Codex conversation, the clipboard has multiple items,
the native link isn't available, the session directory has been removed,
or Warp does not confirm that the tab's startup command is running, the
action fails **without quitting Desktop**. If quitting is blocked or the
session lock remains held for 45 seconds, the tab reports an actionable
error. A real end-to-end Desktop/Warp smoke test is required before
claiming the quit/lock handoff works on a particular Mac.

## Recent Codex chats in Warp

After `chezmoi apply`, Hammerspoon opens up to ten recent local Codex chats
in a dedicated Warp window when Warp launches. Warp uses vertical tabs by
default when applying to a machine without an existing Warp settings file.
In Warp, `Cmd+R` replaces the managed chat window and `Cmd+T` opens a new
Codex chat in a new tab.

All three actions use `codex` by default. To select the bundled voice fork
on this Mac, save its executable name in the local override file.

```sh
mkdir -p ~/.config/warp-codex
printf '%s\n' codex-voice > ~/.config/warp-codex/command
```

The file can also contain a quoted executable path and optional arguments.
The executable must support `app-server` and `resume` to restore recent
chats from its session store. The launcher reads the override on each
invocation. Delete the local override file to return to `codex`.

## AGENTS.md freshness warnings

The desktop shortcut and Codex hooks call the
[same three-stage pipeline](../../home/dot_codex/hooks-json/agents-md-freshness/pipeline.py).
The desktop card displays all three comparisons. The automatic hooks issue a
guidance alert for a confirmed file or session mismatch. A separate repository
alert reports different local and remote `main` commits. Each alert suppresses
repeats independently for the session.

- **Missing evidence:** Stays `unknown` and never silently becomes `current`. A disconnected remote or missing session snapshot does not itself trigger a warning.
- **Safety:** All checks are read-only, asynchronous, and advisory. No `git pull`, `chezmoi apply`, or model-visible instructions are injected. The bedtime guard remains a separate synchronous hook.
- **Scope:** Global instructions only. Project-level `AGENTS.md` files and the model's private inference context are not verified.

To inspect a particular session manually:

```bash
python3 ~/.codex/hooks-json/agents-md-freshness/check.py --check \
  --session-id YOUR_SESSION_ID
```

The result is JSON with `current`, `outdated`, or `unknown`, plus hashes
and (when available) the generated source digests. The check uses the
session's specific rollout, not the newest unrelated chat.

To inspect all three stages outside the desktop shortcut:

```bash
python3 ~/.codex/hooks-json/agents-md-freshness/pipeline.py \
  --session-id YOUR_SESSION_ID
```

After `chezmoi apply`, restart Codex to discover the new hooks and review
their changed definitions via `/hooks`; Codex skips untrusted user hooks.
Mac notifications also depend on macOS notification permissions for the
invoking application. Source snapshots are internal rollout records and may
change format in future Codex releases.

## Portable custom Codex Voice CLI

The normal Homebrew-installed `codex` remains untouched. The separate
`codex-voice` launcher runs a version-pinned, voice-enabled build of the
[personal Codex fork](https://github.com/ArthurZakirov/codex), with
`CODEX_REALTIME_VERBATIM_SPEECH=1`. Codex account authentication stays local.

### Release production

The fork's
[portable Codex Voice workflow](https://github.com/ArthurZakirov/codex/blob/feat/portable-codex-voice-release/.github/workflows/portable-codex-voice.yml)
builds the app from the workspace's pinned Rust toolchain and the voice helper
and native runtime from the repository's existing Bazel/voice packaging
pipeline. It validates native library receipts, build commits, package hashes
and target architecture before publishing a **prerelease** for Apple Silicon
macOS. The packaging process runs in GitHub Actions; fresh Macs do not need
Rust, Cargo, Bazel or GStreamer installed separately.

Preview artifacts are **not Apple Developer ID signed or notarized**. They
are unsuitable for managed/public distribution without a signing and Gatekeeper
validation step. An interactive macOS Gatekeeper decision may be required on
first launch; never disable Gatekeeper system-wide.

### Version pin and installation

The checked-in [codexVoice settings](../../home/.chezmoidata.toml) own the
release version and the installation toggle. To check them:

```sh
grep -A4 '^\[codexVoice\]' home/.chezmoidata.toml
```

The release selected by `codexVoice.tag` is **enabled by default**.
The [checked-in configuration](../../home/.chezmoidata.toml) is the source of
truth for the currently verified version; this guide deliberately does not
duplicate a release tag that would become stale on the next upgrade.
A single `chezmoi apply` installs the pinned release if missing and verifies
an existing installation before skipping it. This applies to both personal
and professional profiles. Set `codexVoice.enabled = false` only to opt out
of automatic provisioning; the launcher alone cannot run without its package.
Change `codexVoice.tag` only to another published and tested release.

Chezmoi installs the
[launcher](../../home/dot_local/bin/executable_codex-voice), the
[stdlib-only installer](../../home/dot_local/bin/executable_codex-voice-install)
and the [after-hook](../../home/run_after_45-install-codex-voice.sh.tmpl).
The hook uses Python 3.11+ from `PATH` (including pyenv/asdf), falling
back to Homebrew Python when necessary. It installs the architecture-specific
macOS release into `~/.local/share/codex-voice/` and preserves both the normal `codex`
and the separate development builds in `~/.local/share/codex-voice-experiment/`.
The release tarball is SHA-256 checked against the release's
`SHA256SUMS`, inspected for unsafe paths, validated against the embedded
voice package manifest, and installed with a rollback of the preceding
package. Verification includes the CLI, code-mode host, exec server, bundled
ripgrep and native word-position speech helper; a missing or damaged tool
causes reinstallation. Reapplying the same intact tag skips the download.

To verify the actual release with Chezmoi in an isolated HOME on macOS
(without changing the current Codex installation), run:

```sh
RUN_CODEX_VOICE_SYSTEM_E2E=1 poetry run pytest -q tests/integration/test_codex_voice_system.py
```

This checks the download, package integrity, launcher, voice helper and
repeated installation. Microphone capture, playback and interactive model
selection still require a manual voice session.

After applying the pinned release:

```sh
codex-voice
```

The launcher supplies `--no-daemon` automatically. This keeps the session on
the installed Voice package's embedded server instead of a separately managed
background server that may run another build. Passing `--no-daemon` explicitly
also works; the launcher avoids adding it twice. An explicit `--remote`
connection is forwarded without adding `--no-daemon`. Commands, file editing and
skills remain available in this mode.

A fresh Mac still needs Codex account login and macOS microphone permission.
Speech uses installed macOS voices, preferring a German Premium voice when
available; install that voice in macOS to reproduce its quality on another Mac.
These per-device permissions and voice downloads are separate from the release
archive.

Use `/model` to verify the model list. Then test microphone permissions,
live speech capture, audio playback and voice controls. Use
`codex --version` to check the unaffected Homebrew Codex installation.

The exact release can be checked with:

```sh
gh release view "$(sed -n 's/^    tag = "\([^"]*\)"/\1/p' home/.chezmoidata.toml)" \
  --repo ArthurZakirov/codex
```

This installer tracks the pinned release tag. It does not automatically
rebase the source fork onto newer upstream Codex versions or establish
compatibility for future model catalogs; upgrades require their own verified
release.

## Global voice shortcuts

Option+1 sends F8 to the last focused Herdr window, then restores the previous app. To target Warp instead, set `"terminal_app": "Warp"` in `~/.config/codex-voice/config.json` and reload Hammerspoon. The default is `"Herdr"`. Option+Shift+Return sends directly to the dictating Codex session in either terminal.
