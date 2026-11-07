# 🔎 Find Codex sessions from Git context

Use `session-find` to find Codex conversations by the Git artifact you already have: a repository, worktree, branch, commit, pull request or Jira issue key.

This is a **search core**, not a desktop window manager. It does not open chats or depend on Hammerspoon, Chrome or VS Code.

## ▶️ Examples

After applying the managed executable with Chezmoi, run:

```bash
session-find --repo dotfiles
session-find --repo ~/Repos/dotfiles
session-find --repo https://github.com/ArthurZakirov/dotfiles
session-find --worktree ~/Repos/dotfiles.worktrees/feat-example
session-find --branch feat/example
session-find --commit abcdef1
session-find --pr https://github.com/ArthurZakirov/dotfiles/pull/2
session-find --pr https://bitbucket.org/workspace/repo/pull-requests/8
session-find --jira DCP-9712
session-find --repo dotfiles --branch feat/example --json
```

Multiple filters are combined with AND: a session must match every supplied artifact. Results include the Codex session ID, relative confidence, exact evidence source and a suggested `codex resume <session-id>` command. The program **does not** execute that command.

## 🧩 Where results come from

The [Python CLI](../../home/dot_local/bin/executable_session-find) reads existing Codex SQLite files from `$CODEX_HOME` or `~/.codex` in read-only mode:

| Source | Recorded evidence | Meaning |
| --- | --- | --- |
| `state_5.sqlite` → `thread_attachments` | Attached PR URL | Direct PR-to-session link |
| `state_5.sqlite` → `threads` | Starting Git remote, branch, commit, working directory | Context at session creation, not all later work |
| `thread_history_1.sqlite` → `fileChange` | Edited file paths | Strong evidence of repository/worktree activity |
| `thread_history_1.sqlite` → `commandExecution` | Command execution directory | Repository activity, not proof of a change |
| Session text and history messages | Branch, SHA, PR or Jira references | A mention, not proof of implementation |
| `thread_spawn_edges` | Related parent/child sessions | Navigation context, not automatic inheritance of Git evidence |

A single session can match several repositories. Conversely, one repository or PR can lead to multiple sessions. Results expose evidence and do not silently turn hints into verified implementation links.

## 🛠️ Installation and validation

The executable is managed by Chezmoi as `~/.local/bin/session-find`. From a Dotfiles feature worktree, preview and install **only this executable** (do not apply the whole profile):

```bash
chezmoi --source "$PWD/home" apply --dry-run --verbose ~/.local/bin/session-find
chezmoi --source "$PWD/home" apply ~/.local/bin/session-find
session-find --pr https://github.com/ArthurZakirov/dotfiles/pull/2
```

Check that `~/.local/bin` is on your `PATH`. For isolated synthetic tests, run:

```bash
python3 -m unittest discover -s tests/unit -p test_session_find.py -v
```

The CLI uses only Python's standard library; no database server, index or package installation is needed. It never writes into the Codex databases. `--codex-home` selects a non-default source location.

## ⚠️ Scope and limitations

- The Codex SQLite schema is internal and may change in future versions. Search cannot recover events that were never recorded.
- A worktree name and a repository name are not globally unique. Historical or deleted checkouts may need better remote-identity resolution; do not mistake a name-based match for a confirmed Git remote.
- A branch, commit or Jira key mentioned in text is weak evidence. The current implementation does **not** reconstruct commit history, query GitHub/Jira APIs or follow all command side effects.
- This version searches **Codex only**. ChatGPT and ChatGPT Work require separate provider adapters; linking and opening chats are not implemented.
- Results may contain private session titles and local file paths. Avoid publishing unredacted JSON output.
