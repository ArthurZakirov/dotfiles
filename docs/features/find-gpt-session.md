# 🔎 find-gpt-session — unified session search

`find-gpt-session` is one CLI for finding Codex and ChatGPT conversations by Git artifact or remembered text.

## 🧩 Architecture

The Python application core owns query normalization, common session identity, evidence, ranking, provider errors, deduplication and JSON output. Infrastructure adapters implement the same `SessionProvider.search(request, limit)` port:

| Adapter | Source | Current capabilities |
| --- | --- | --- |
| `codex` | Existing local `session-find` Codex history backend | Strong Git context evidence and `codex resume` |
| `safari` | Native macOS Accessibility with Safari's authenticated ChatGPT search | ChatGPT message-text search; opens visible results to verify URLs |
| `chrome` | Same native macOS Accessibility adapter | Opt-in Chrome UI search; may briefly switch the active tab |
| `desktop` | Existing ChatGPT Desktop Accessibility search | Text search suggestions; URLs not yet guaranteed |

These are infrastructure differences, not separate CLI/domain logic. The current Codex/Desktop adapters reuse the existing installed `session-find` implementation while those provider internals are being migrated.

## Usage

```sh
find-gpt-session --pr "https://github.com/ArthurZakirov/dotfiles/pull/67" --provider safari
find-gpt-session --branch "feat/my-branch" --provider codex
find-gpt-session search "worktree cleanup" --provider safari --json
find-gpt-session --jira DCP-123 --provider desktop
find-gpt-session --pr "https://github.com/ArthurZakirov/dotfiles/pull/2" --provider all
```

Without `--provider`, the CLI searches Codex plus Safari. Repeat `--provider` to select more. The browser is never inferred from the Git query; only the provider selection determines infrastructure.

For PR URLs, browser adapters search the recognizable path fragment (for example `pull/67`) in **ChatGPT's own message and title search**. For free text, they pass your keywords to the same search; it is **not** an embedding-based semantic fuzzy search, and coverage depends on ChatGPT's own search index.

## ⌨️ Open related sessions from the current Git context

Press **Ctrl+Option+Cmd+S** while a GitHub/Bitbucket PR or branch page is active in Chrome, or while a Git worktree is open in VS Code. No search dialog or Raycast command is needed.

1. Hammerspoon obtains the actual GitHub/Bitbucket URL from Chrome (including installed Chrome web apps), or delegates to the global VS Code task to supply the precise workspace path.
2. The same `find-gpt-session` core resolves a PR, branch or repository and searches Codex plus ChatGPT via Safari.
3. Every returned **Codex** hit opens a new tab in the active Warp window and runs `codex resume <UUID>`. Warp starts if it is not already running.
4. Every returned **ChatGPT** hit with a verified `chatgpt.com/c/...` URL opens a new tab in the active Chrome window. Chrome starts if necessary. A hit without a verified URL is skipped with a warning.

The underlying command is still the single CLI; `--open` changes the action from listing to opening:

```sh
find-gpt-session --open --context-url "https://github.com/ArthurZakirov/dotfiles/pull/67"
find-gpt-session --open --context-path "$PWD"
find-gpt-session --open search "worktree cleanup"
```

Normal listing defaults to eight results; opening defaults to 25, with `--limit` available to override the cap. Search backends can still return fewer results, especially Safari in the background. No additional Raycast extension or separate search engine is installed. Opening is a **dispatched** OS action and is not misrepresented as a confirmed successful Codex login. Partial ChatGPT background coverage still applies.

Warp uses its supported `warp://tab_config/...` deep links and standard per-tab startup commands rather than injecting keystrokes into a potentially busy terminal. Runtime configs containing resume IDs are written mode 0600 under `~/.warp/tab_configs/` and older generated configs are pruned on subsequent launches. No session IDs are stored in public Dotfiles source.

`Option+Cmd+Space` is already assigned to Finder search on macOS; the new shortcut uses the existing Hammerspoon Hyper family to avoid silently overriding that system binding.

## ⚠️ Limitations and data safety

The browser backends are experimental: UI structure, content availability and macOS background Accessibility can change. Safari was verified to find a chat from the body-text query `pull/67`, open it and retrieve its direct URL, but reopening the search after navigating can fail while Safari is in the background. When Safari is in the background, only the first navigated result is currently reliable; the adapter stops after that result and reports incomplete coverage. A missing verified URL produces an explicit warning; never assume the entire cloud history was searched.

The native macOS adapter is compiled from its Chezmoi-managed Swift source on first use and cached at `~/.cache/find-gpt-session/ui-ax`, so later CLI calls do not recompile. Browser operations may navigate the selected browser tab. The Chrome backend requires an existing signed-in ChatGPT tab and restores the prior tab only if it was not changed concurrently.

Codex history uses existing local databases read-only. No new persistent search database is created. Browser adapters use macOS Accessibility and tab URLs; they do not extract cookies, tokens or passwords, call undocumented ChatGPT APIs, or upload conversation content. Do not commit private chat-URL results to public repositories.

The CLI's incomplete_providers field distinguishes incomplete coverage from verified zero matches. When a provider cannot return a verified result, **search_status: incomplete** is reported in JSON and the human-readable output says **“Search incomplete”**, rather than incorrectly reporting **“Found 0 sessions”**; the exit status is 2. A confirmed no-match result uses exit status 1, while a hit uses 0. The Safari navigation adapter reads URL and title together, waits up to 12 seconds for a verified result, and also accepts a new, stable conversation URL after explicitly clicking a visible search result if the page title is slow to update. Regression tests cover delayed navigation and title updates.

For truly unattended background operation and faster repeated result extraction, additional browser automation capability must be validated without affecting the user's active Chrome tab. Background Safari may still hide its Accessibility search controls, in which case the query remains incomplete rather than falsely returning zero matches.
\n### Background Safari timeouts\n
Safari Apple Events can block when its tab is in the background. The native
browser adapter now bounds each AppleScript child to 2.5 seconds and the
overall provider search to 18 seconds. An unresponsive Safari is marked as
incomplete instead of indefinitely preventing already-discovered Codex
sessions from being opened. The Hammerspoon module exposes runtime-only
diagnostics (status and counts, not private chat text/URLs) for troubleshooting.


### Verified workflow and pending interaction test

A live GitHub PR #2 test entered the Hammerspoon handler, searched Codex and
ChatGPT, and opened one matching Codex session in Warp. After limiting the
Safari AppleScript and overall browser search timeouts, the handler completed
in approximately 13.6 seconds rather than stalling for about 90 seconds.
An unavailable Safari search was reported as incomplete; the Codex result was
still opened. A physical keyboard shortcut press remains user-verification
work; a synthetic macOS keyboard event was not conclusive.


### Optional Codex text-search integration

The Codex transcript-search module is developed independently under AGENT-5.6.
When its managed `codex_text.py` is installed, `CodexProvider` uses it for
free-text queries. This opening feature intentionally does not overwrite or
duplicate the parallel branch's module; a fresh checkout without that module
reports incomplete Codex keyword coverage rather than silently losing
existing support on the private Mac.


### Hotkey feedback when a PR has no verified session

The global `Ctrl+Option+Cmd+S` shortcut is separate from session discovery.
A GitHub/Bitbucket PR can have **zero indexed local Codex sessions** even if
the PR exists. Safari can also be unavailable in the background, making the
ChatGPT side incomplete. In that situation the Hammerspoon UI explicitly says
**"Keine Codex-Session gefunden; ChatGPT-Suche derzeit nicht verfügbar."**
instead of calling it a failed shortcut. The adapter consumes the same
structured JSON output as the CLI and distinguishes confirmed no matches,
partial coverage, unopenable hits, and sessions that actually opened. No
conversation URLs, message content, or search text are stored in diagnostics.

This is a feedback correctness fix, not a replacement for the incomplete
background ChatGPT provider (tracked separately in AGENT-5.7).


### Safari foreground Accessibility recovery (PR #65 regression)

On macOS, **Safari can be running, logged into ChatGPT and displaying a
conversation while exposing no usable Accessibility tree when inactive**.
This was the actual failure behind the Ctrl+Option+Cmd+S false-negative on
GitHub PR #65: a native UI search for `pull/65` returned no results in the
background. With Safari foregrounded, the same search returned a verified
matching ChatGPT URL.

The native Safari adapter now activates Safari briefly during the search and
restores whichever app was frontmost before it, **unless the user changes the
foreground app during the search**. Safari's own logged-in tab is reused. This
does **not** require JavaScript-from-Apple-Events permission, cookie access or
a permanent browser automation tab. Temporary Safari focus is a known
tradeoff; reliably invisible multi-hit search remains AGENT-5.7 work.

Verified locally: with Warp frontmost, the `pull/65` query found its
ChatGPT conversation in approximately 3.3 seconds and returned focus to Warp.
The full `find-gpt-session --open --context-url <PR URL>` command subsequently
opened that verified conversation in a new tab **in the existing Chrome
window**, from one tab to two. Regression checks also exercise the live
Hammerspoon callback and native Swift self-test.


### Prepared Safari search for fast repeated hotkeys

The existing Hammerspoon instance prewarms ChatGPT search in the already-running,
signed-in Safari tab once after its configuration loads, and also when Safari
starts later. No LaunchAgent, additional browser window, recurring foreground
polling, credentials access or unofficial ChatGPT API is required.

```sh
find-gpt-session --prepare-safari --json
# {"prepared": true, "warning": null} when the search field is ready
```

The native Swift adapter checks whether the Accessibility `AXComboBox Search`
already exists. If ready, the next search enters its query **without first
pressing ChatGPT's Search button**, and without foregrounding Safari when
background AX input is supported by the OS. Otherwise, it waits for the actual
Search button and field using bounded state polling, rather than typing during
an animation or relying on a fixed sleep. A foreground fallback remains for
macOS builds which conceal the browser's web Accessibility tree in the background.

The adapter reopens the search dialog after navigation, *before* restoring
focus to Chrome/VS Code. If a hotkey arrives while the startup prewarming
process is still active, Hammerspoon queues the request and sends it after
that process finishes instead of racing two concurrent AX actions.

**Limitations:** Initial prewarming can briefly activate Safari, then restore
the original foreground application. This is an opportunistic optimization,
not a guarantee of background AX access or zero-latency network search.
A browser restart, a user-closing the search overlay, or a login/loading
screen can invalidate readiness; the ordinary on-demand path remains.
The background multi-result URL resolution is still tracked separately
under AGENT-5.7.

**Validation status:** Source implementation and provider/CLI/LuaJIT regression
tests were prepared via the GitHub connector while Mac Remote Desktop
Commander was quota-blocked. The physical shortcut, Safari UI readiness and
Chrome-tab outcome **must be tested on the actual Mac before this feature is
called working or the PR is merged**.
