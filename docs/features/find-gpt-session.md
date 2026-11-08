# 🔎 find-gpt-session — unified session search

`find-gpt-session` is one CLI for finding Codex and ChatGPT conversations by Git artifact or remembered text.

## 🧩 Architecture

The Python application core owns query normalization, common session identity, evidence, ranking, provider errors, deduplication and JSON output. Infrastructure adapters implement the same `SessionProvider.search(request, limit)` port:

| Adapter | Source | Current capabilities |
| --- | --- | --- |
| `codex` | Local Codex state and transcript SQLite (read-only); existing `session-find` for Git context | Git activity and keyword matches in titles, prompts, user/assistant messages; `codex resume` |
| `safari` | Native macOS Accessibility with Safari's authenticated ChatGPT search | ChatGPT message-text search; opens visible results to verify URLs |
| `chrome` | Same native macOS Accessibility adapter | Opt-in Chrome UI search; may briefly switch the active tab |
| `desktop` | Existing ChatGPT Desktop Accessibility search | Text search suggestions; URLs not yet guaranteed |

These are infrastructure differences, not separate CLI/domain logic. For Codex, Git-artifact queries delegate to the existing `session-find` backend, while keyword searches read native Codex messages and metadata directly. The ChatGPT Desktop adapter also reuses the existing `session-find` UI integration.

## Usage

**Global search is the default.** No need to know whether a conversation was in Codex or ChatGPT:

```sh
find-gpt-session search "worktree cleanup"
find-gpt-session --pr "https://github.com/ArthurZakirov/dotfiles/pull/67"
find-gpt-session search "worktree cleanup" --json

# Optionally restrict the infrastructure:
find-gpt-session --pr "https://github.com/ArthurZakirov/dotfiles/pull/67" --provider safari
find-gpt-session --branch "feat/my-branch" --provider codex
find-gpt-session search "worktree cleanup" --provider safari --json
find-gpt-session --jira DCP-123 --provider desktop
find-gpt-session --pr "https://github.com/ArthurZakirov/dotfiles/pull/2" --provider all
```

Without `--provider`, the CLI searches **Codex and ChatGPT via Safari** and combines the results. Repeat `--provider` to select more. The browser is never inferred from the Git query; only the provider selection determines infrastructure. If both products have matches, the ranking reserves a result from each when the result limit allows it.

For PR URLs, browser adapters search the recognizable path fragment (for example `pull/67`) in **ChatGPT's own message and title search**. For free text, they pass your keywords to the same search. Codex searches local titles, previews, user and assistant messages; multiple keywords can match across turns of the same conversation. Neither side is an embedding-based semantic fuzzy search. Codex is limited to locally recorded sessions; ChatGPT coverage depends on its own search index and Safari's background accessibility.

## ⚠️ Limitations and data safety

The browser backends are experimental: UI structure, content availability and macOS background Accessibility can change. Safari was verified to find a chat from the body-text query `pull/67`, open it and retrieve its direct URL, but reopening the search after navigating can fail while Safari is in the background. When Safari is in the background, only the first navigated result is currently reliable; the adapter stops after that result and reports incomplete coverage. A missing verified URL produces an explicit warning; never assume the entire cloud history was searched.

The native macOS adapter is compiled from its Chezmoi-managed Swift source on first use and cached at `~/.cache/find-gpt-session/ui-ax`, so later CLI calls do not recompile. Browser operations may navigate the selected browser tab. The Chrome backend requires an existing signed-in ChatGPT tab and restores the prior tab only if it was not changed concurrently.

Codex history uses existing local databases read-only. No new persistent search database is created. Browser adapters use macOS Accessibility and tab URLs; they do not extract cookies, tokens or passwords, call undocumented ChatGPT APIs, or upload conversation content. Do not commit private chat-URL results to public repositories.

The CLI's incomplete_providers field distinguishes incomplete coverage from verified zero matches. When a provider cannot return a verified result, **search_status: incomplete** is reported in JSON and the human-readable output says **“Search incomplete”**, rather than incorrectly reporting **“Found 0 sessions”**; the exit status is 2. A confirmed no-match result uses exit status 1, while a hit uses 0. The Safari navigation adapter reads URL and title together, waits up to 12 seconds for a verified result, and also accepts a new, stable conversation URL after explicitly clicking a visible search result if the page title is slow to update. Regression tests cover delayed navigation and title updates.

For truly unattended background operation and faster repeated result extraction, additional browser automation capability must be validated without affecting the user's active Chrome tab. Background Safari may still hide its Accessibility search controls, in which case the query remains incomplete rather than falsely returning zero matches.
