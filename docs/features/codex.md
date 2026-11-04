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

The results are displayed as five independent green / red / unknown stages:

| Stage | Verified contract |
| --- | --- |
| **GitHub main** | `git ls-remote origin refs/heads/main` obtains the real GitHub commit (not merely a stale local remote-tracking ref). |
| **Lokales main** | The local `main` commit matches GitHub and the actual checked-out managed guidance file equals `main`'s committed version. |
| **Guidance erzeugt** | The versioned `AGENTS.md.tmpl` and references match the canonical guidance manifest/components, using `render.py --check` in the Dotfiles Python environment. |
| **Chezmoi apply** | The actual `~/.codex/AGENTS.md` bytes match `chezmoi --source <checkout>/home cat ~/.codex/AGENTS.md`, including profile-specific template rendering. |
| **Codex-Kontext** | The current session's most recently recorded model-visible global instructions match `~/.codex/AGENTS.md`, using the [chezmoi-managed session checker](../../home/dot_codex/hooks-json/agents-md-freshness/executable_check.py). |

Each stage reports what is *actually* known; inability to contact GitHub,
find a usable project Python environment, or identify the session is
**unknown**, not green. Later local stages remain visible even if GitHub
is unavailable. The pipeline never runs `git fetch`, `chezmoi apply`,
regenerates guidance, or changes Codex state. It does **not** guarantee
the private inference context or project-level `AGENTS.md` freshness.

The final card appears only once all checks complete (no intermediate blue
flashing). It closes after about three seconds if all stages match, or
four seconds when outdated/unverifiable. The app stays focused; the
shortcut preserves supported clipboard formats when the native deep link is
copied and avoids overwriting unrelated clipboard changes.

This first version supports local Codex chats in the desktop application
(bundle ID `com.openai.codex`), not terminal Codex sessions or unrelated
ChatGPT conversations.

## AGENTS.md freshness warnings

The desktop shortcut and Codex hooks call the
[same five-stage pipeline](../../home/dot_codex/hooks-json/agents-md-freshness/pipeline.py):

| Stage | What is verified |
| --- | --- |
| **GitHub main** | The remote default-branch commit is obtainable via Git. |
| **Lokales main** | Local main and the managed guidance checkout agree with GitHub. |
| **Guidance erzeugt** | Generated guidance matches the canonical source components. |
| **Chezmoi apply** | Installed `~/.codex/AGENTS.md` matches the rendered chezmoi template. |
| **Codex-Kontext** | This session's last recorded model-visible instructions match the installed file. |

- **Desktop shortcut:** Always displays all five statuses, including `unknown`.
- **Automatic hooks:** `UserPromptSubmit` and `Stop` call that same read-only pipeline; confirmed `outdated` stages produce a Codex UI `systemMessage` and macOS notification. Repeated notifications for the same session and mismatch are suppressed.
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

To inspect all five stages outside the desktop shortcut:

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
and Intel Macs. The packaging process runs in GitHub Actions; fresh Macs do
not need Rust, Cargo, Bazel or GStreamer installed separately.

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

After the release exists and the package has passed CI and a real voice
session smoke test, set `codexVoice.enabled = true` and update
`codexVoice.tag` to the **published** tag. The initial setting is disabled
until that release is verified. Commit this update before relying on fresh
Mac onboarding.

Chezmoi installs the
[launcher](../../home/dot_local/bin/executable_codex-voice), the
[stdlib-only installer](../../home/dot_local/bin/executable_codex-voice-install)
and the [after-hook](../../home/run_after_45-install-codex-voice.sh.tmpl).
The hook installs the macOS-architecture-specific release into
`~/.local/share/codex-voice/` and preserves both the normal `codex`
and the separate development builds in `~/.local/share/codex-voice-experiment/`.
The release tarball is SHA-256 checked against the release's
`SHA256SUMS`, inspected for unsafe paths, validated against the embedded
voice package manifest, and installed with a rollback of the preceding
package. Reapplying the same tag skips the download.

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
codex-voice --no-daemon
```

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
