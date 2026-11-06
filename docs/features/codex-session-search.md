# Find Codex sessions by Git context

[← Feature index](README.md) · [Development workflow](../../docs/development.md)

The `session-find` CLI locates existing **Codex** conversations by repository, worktree, branch, commit, PR URL or Jira key. It searches Codex's native local SQLite files read-only, not only the directory where a session was started. A single session can appear under multiple repositories.

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

## Evidence and limits

- **Direct:** a PR attached to a Codex thread.
- **File activity:** a recorded file change within the queried repository/worktree.
- **Context:** a command's working directory, or Git branch/remote/SHA captured at session start.
- **Mention:** a text reference in a recorded message, title or command.

Evidence scores rank matches, not probabilities. A mention or a command working directory does **not** prove that a session implemented a change. A branch captured at startup may differ from branches used later. Session IDs are retained even when a worktree is deleted. Exact PR searches require a recorded PR attachment or a literal matching PR URL; they do not assume every session in a repository belongs to the PR.

Codex stores these records under `~/.codex/state_5.sqlite` and `~/.codex/thread_history_1.sqlite`. The second file is optional; if unavailable, activity-based matches are omitted with a warning. The native schemas are private implementation details and may change after a Codex update. The CLI uses Python's standard library, requires no server, and creates **no additional database or index**. It never contacts GitHub, Bitbucket, Jira, ChatGPT or Work.

`--codex-home /path/to/.codex` overrides the data location for testing or another local Codex profile. Results are limited to locally recorded Codex sessions; ChatGPT and Work are not yet indexed. Nonstandard repository layouts, ambiguous repository names and activity outside recorded tool events can lead to incomplete or uncertain matches.

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
