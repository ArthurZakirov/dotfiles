# 🔎 find-gpt-session — find and open related conversations

`find-gpt-session` searches Codex and ChatGPT conversations by Git context or remembered keywords. **Ctrl+Option+Cmd+S** opens the matching conversations from a GitHub/Bitbucket page in Chrome or a Git worktree in VS Code.

## 🧩 Components and installation

Chezmoi manages every required source component in this repository:

| Component | Responsibility | Managed source |
| --- | --- | --- |
| `find-gpt-session` | User CLI, provider selection, JSON and opening | [CLI](../../home/dot_local/bin/executable_find-gpt-session) |
| `find_gpt_session` | Query normalization, ranking, adapters and launchers | [Package](../../home/dot_local/lib/find_gpt_session/) |
| `session-find` | Independently usable Codex Git-history backend and optional Desktop suggestions | [Backend CLI](../../home/dot_local/bin/executable_session-find) |
| `codex_history` | Private SQLite snapshots shared by the readers | [SQLite reader](../../home/dot_local/lib/codex_history/sqlite.py) |
| Native browser adapter | Accessibility search and verified chat URLs | [Swift source](../../home/dot_local/share/find-gpt-session/ui.swift) |
| Hammerspoon integration | Global shortcut and one-time Safari preparation | [Hotkey module](../../home/dot_hammerspoon/modules/gpt_sessions.lua) |

Git-artifact queries delegate to the adjacent managed `session-find` executable, independently of the GUI shell's `PATH`. Codex keyword queries use the bundled [transcript adapter](../../home/dot_local/lib/find_gpt_session/codex_text.py). Neither component depends on an uncommitted local installation.

The browser adapter compiles with Apple's command-line developer tools on first use and caches its executable under `~/.cache/find-gpt-session/`. Browser search requires an authenticated ChatGPT tab and macOS Accessibility access. Opening Codex sessions requires Warp and the configured Codex CLI. The optional Desktop provider requires Peekaboo. These applications, account sessions and OS permissions remain setup prerequisites; the feature does not copy credentials or grant permissions.

## 🔍 Search

Use the shared CLI for combined results or select a provider explicitly:

```sh
find-gpt-session search "worktree cleanup"
find-gpt-session --pr "https://github.com/ArthurZakirov/dotfiles/pull/67" --json
find-gpt-session --branch "feat/my-branch" --provider codex
find-gpt-session search "worktree cleanup" --provider safari --json
```

The default providers are `codex` and `safari`. Repeat `--provider` to combine sources or use `--provider all` to include the opt-in Chrome and Desktop adapters. Ranking retains a result from each product when the limit permits.

Codex searches local Git metadata, file activity and text mentions, or titles and user/assistant messages for keyword queries. ChatGPT uses its own title/message search; a PR query becomes a path fragment such as `pull/67`. These are evidence-based searches rather than semantic similarity searches. Common default-branch pages such as `/tree/main` use repository context to avoid opening unrelated `main` sessions.

## ⌨️ Open results

Press **Ctrl+Option+Cmd+S**, or run one of these equivalent commands:

```sh
find-gpt-session --open --context-url "https://github.com/ArthurZakirov/dotfiles/pull/67"
find-gpt-session --open --context-path "$PWD"
find-gpt-session --open search "worktree cleanup"
```

The opening sequence is:

1. Resolve the source PR, branch or repository and search the selected providers.
2. Open each verified Codex ID in a new Warp tab using `codex resume <UUID>`.
3. Open verified ChatGPT URLs in new tabs of the existing Chrome window and activate Chrome.
4. If any Codex tabs opened, activate Warp last. Mixed results therefore leave Warp with keyboard focus; both products have their new tabs ready.

The CLI reports dispatches and errors separately. Dispatch does not establish that Codex login or conversation loading has completed. Unverified suggestions are skipped. A failure to activate Warp is reported even when its tab was dispatched successfully.

Warp uses supported `warp://tab_config/...` links rather than typing into a busy terminal. Generated tab configurations have mode `0600`; old generated configurations are pruned on subsequent launches. Listing defaults to eight results and opening to 25; `--limit` changes the cap.

## ⚡ Prepared Safari search

Hammerspoon prepares the search overlay once after configuration load and when Safari launches later. It uses the existing authenticated ChatGPT tab; it does not start a polling daemon or another browser. To request preparation directly:

```sh
find-gpt-session --prepare-safari --json
```

The adapter selects an existing ChatGPT tab/window before reading Accessibility controls or verifying navigation. It restores the previous Safari tab/window selection if the user has not changed it concurrently. No ChatGPT tab means an explicit incomplete result.

A ready Search field receives the query immediately. Otherwise the adapter waits for the actual control, rather than typing after a fixed animation delay. It can briefly foreground Safari when macOS hides its Accessibility tree, then restore the previous app. It reopens the overlay after navigating to results. An early hotkey is queued with its original PR URL while preparation finishes.

Preparation is opportunistic: login/loading screens, closing the overlay, browser restarts and OS Accessibility failures can invalidate readiness. The normal search path remains available. Fully invisible multi-result browser search is not guaranteed.

## ⚠️ Coverage and data safety

Browser results are partial. In the background, Safari may expose only the first navigated result; missing controls or unverified URLs are reported as incomplete rather than confirmed absence. ChatGPT's own search index can also omit messages.

Each AppleScript child is bounded to 2.5 seconds. The browser process allowance scales with the capped result count: 30 seconds of setup plus 30 per result, up to 12 results. This permits the 12-second navigation verification per-result UI polling and URL roundtrips to finish without discarding all collected hits at an arbitrary 18-second cutoff.

Codex readers capture private temporary SQLite snapshots, including committed WAL data. SQLite creates any working sidecars only in scratch storage; the source history remains untouched. No persistent search database is added. Browser adapters use Accessibility and tab URLs without extracting cookies/passwords, enabling JavaScript from Apple Events, calling undocumented ChatGPT APIs or uploading conversations.

JSON distinguishes `matches`, `partial`, `incomplete` and `no_matches`. Exit status is `0` for hits, `1` for confirmed no matches and `2` for incomplete searches or opening failures. Hammerspoon displays the corresponding status without persisting query text or chat URLs.

## 🧪 Validation

[Chezmoi lifecycle tests](../../tests/integration/test_chezmoi_lifecycle.py) install the full managed tree into disposable homes for both profiles, then execute the installed Git and keyword search entry points against synthetic history. This catches missing executables/modules and accidental fallback to a developer's existing installation.

[Backend contracts](../../tests/unit/test_session_find.py) cover artifact boundaries, URI-significant paths and WAL snapshots without source writes. [Opening contracts](../../tests/unit/test_session_open.py) cover safe launch configuration, context scoping and Warp activation after Chrome. [Hotkey contracts](../../tests/unit/test_hammerspoon_gpt_sessions.py) cover preparation and queued requests. The native Swift self-test covers delayed URL/title navigation.

The user confirmed the physical shortcut works on the private Mac. Automated installation tests use synthetic data and do not imply exhaustive coverage of cloud history or every macOS Accessibility state.
