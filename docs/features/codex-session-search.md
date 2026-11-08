# 🔎 Find Codex and ChatGPT sessions by Git context

[← Feature index](README.md) · [Development workflow](../../docs/development.md)

The `session-find` CLI locates existing **Codex** conversations by repository, worktree, branch, commit, PR URL or Jira key. It searches Codex's native local SQLite files read-only, not only the directory where a session was started. A single session can appear under multiple repositories. An optional macOS adapter also searches the **visible ChatGPT desktop search results** (including Work results when the app shows them).

## Use

After applying the managed executable to this Mac:

```sh
session-find --repo dotfiles
session-find --repo ~/Repos/dotfiles
session-find --repo git@github.com:ArthurZakirov/dotfiles.git
session-find --worktree ~/Repos/dotfiles.worktrees/feat-example
session-find --repo dotfiles --branch feat/example
session-find --pr https://github.com/ArthurZakirov/dotfiles/pull/2
session-find --jira DCP-9712
session-find --commit abcdef1
session-find --repo dotfiles --json
```

Inputs are combined with AND: `--repo X --branch Y` requires evidence for both in the same session. Results show exact Codex session IDs, why they matched, related subagent IDs, and a `codex resume <id>` command. The CLI **does not automatically resume a chat** or focus a window; opening sessions is a separate future integration.

## 🖥️ Optional live ChatGPT search

To search the already-signed-in **ChatGPT desktop app** along with Codex, use:

```sh
session-find --pr https://github.com/ArthurZakirov/dotfiles/pull/67 --chatgpt
session-find --chatgpt-query 'pull/67'
session-find --chatgpt-query 'session-find' --json
```

The `--chatgpt` option converts the Git input into **one visible search term** (e.g. `pull/67`). Unlike Codex's multi-field searches, the ChatGPT UI search does *not* verify that a found chat actually made the Git change, and multiple Git flags are **not** treated as AND conditions for ChatGPT. If you know the exact phrase, prefer `--chatgpt-query`.

This adapter needs the installed `peekaboo` CLI, macOS Accessibility permission, and an open, signed-in ChatGPT desktop window. It uses ChatGPT's real Command-K search field through Accessibility; it may briefly focus the app and leaves the result list open for selection. **No browser debugger, credentials, cookies or internal ChatGPT API calls** are used.

The current Accessibility result list exposes chat titles and ephemeral `⌃1`, `⌃2`, etc. selection positions, **not conversation IDs or permalinks**. The CLI reports `session_id: null` and `chat_url: null` rather than inventing links. Results may be incomplete: the app itself can warn that some cloud messages are missing from search. If the app is absent or the UI changes, the command fails explicitly rather than reporting zero matches. Without `--chatgpt` or `--chatgpt-query`, `session-find` never opens or controls ChatGPT.

## Evidence and limits

- **Direct:** a PR attached to a Codex thread.
- **File activity:** a recorded file change within the queried repository/worktree.
- **Context:** a command's working directory, or Git branch/remote/SHA captured at session start.
- **Mention:** a text reference in a recorded message, title or command.

Evidence scores rank matches, not probabilities. A mention or a command working directory does **not** prove that a session implemented a change. A branch captured at startup may differ from branches used later. Session IDs are retained even when a worktree is deleted. Exact PR searches require a recorded PR attachment or a literal matching PR URL; they do not assume every session in a repository belongs to the PR.

Codex stores these records under `~/.codex/state_5.sqlite` and `~/.codex/thread_history_1.sqlite`. The second file is optional; if unavailable, activity-based matches are omitted with a warning. The native schemas are private implementation details and may change after a Codex update. The CLI uses Python's standard library, requires no server, and creates **no additional database or index**. The default Codex-only search never contacts GitHub, Bitbucket, Jira, ChatGPT or Work. Only the explicitly requested ChatGPT UI adapter invokes the existing app search.

`--codex-home /path/to/.codex` overrides the data location for testing or another local Codex profile. Codex results remain limited to locally recorded Codex sessions. ChatGPT and Work conversations are not locally indexed; live UI suggestions are a separate, explicitly requested source. Nonstandard repository layouts, ambiguous repository names and activity outside recorded tool events can lead to incomplete or uncertain matches.

## Test

```sh
python3 -m unittest discover -s tests/unit -p test_session_find.py -v
```

For a feature-worktree preview without running other chezmoi lifecycle scripts:

```sh
chezmoi --source "$PWD/home" apply --dry-run --verbose ~/.local/bin/session-find
chezmoi --source "$PWD/home" apply ~/.local/bin/session-find
command -v session-find
session-find --repo dotfiles --limit 5
```

Run the last block from the repository's feature-worktree root, and inspect the dry run before applying.
