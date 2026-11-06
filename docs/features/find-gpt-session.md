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

## ⚠️ Limitations and data safety

The browser backends are experimental: UI structure, content availability and macOS background Accessibility can change. Safari was verified to find a chat from the body-text query `pull/67`, open it and retrieve its direct URL, but reopening the search after navigating can fail while Safari is in the background. When Safari is in the background, only the first navigated result is currently reliable; the adapter stops after that result and reports incomplete coverage. A missing verified URL produces an explicit warning; never assume the entire cloud history was searched.

The native macOS adapter is compiled from its Chezmoi-managed Swift source on first use and cached at `~/.cache/find-gpt-session/ui-ax`, so later CLI calls do not recompile. Browser operations may navigate the selected browser tab. The Chrome backend requires an existing signed-in ChatGPT tab and restores the prior tab only if it was not changed concurrently.

Codex history uses existing local databases read-only. No new persistent search database is created. Browser adapters use macOS Accessibility and tab URLs; they do not extract cookies, tokens or passwords, call undocumented ChatGPT APIs, or upload conversation content. Do not commit private chat-URL results to public repositories.

The CLI's `incomplete_providers` field distinguishes incomplete coverage from verified zero matches. For truly unattended background operation and faster repeated result extraction, additional browser automation capability must be validated without affecting the user's active Chrome tab.
