# One Mac-wide agent backlog

The Dotfiles **common** Homebrew profile installs Backlog.md on both personal
and professional Macs. The managed `agent-backlog` command always uses
`$HOME/.local/share/agent-backlog`, independent of the current repository,
working directory or Git worktree. No employer or personal task content is
stored in this public Dotfiles Git repository.

## Open and use

- Press **Option-K** anywhere to toggle the dedicated Hammerspoon Kanban window.
  This is a WebKit window, not another Chrome tab. It opens on the
  **DELL U3225QE** when connected (otherwise the macOS main display),
  and is repositioned every time it reopens.
- Press **Command-K** while the Backlog window is focused to search tasks.
  This search shortcut is enabled only while that window has focus; Command-K
  in other applications keeps its original behavior.
- Press **Escape** to hide the focused Backlog window. **Option-K** still
  toggles the window as before; Escape is not intercepted in other apps.
- The local web service listens on `http://127.0.0.1:6420`. The managed
  `com.arthur.agent-backlog` LaunchAgent starts it at login and restarts it if
  it exits; `chezmoi apply` loads the agent during an active GUI session.
- From **any** directory: `agent-backlog task list --json`, `agent-backlog
  task view AGENT-1 --json`, `agent-backlog task create "Title"`, or
  `agent-backlog board`.
- Separate repositories and external tickets using visible, filterable labels:
  `repo:dotfiles`, `area:personal`, `area:professional`,
  `ticket:ABC-123`. The browser Kanban supports label filters; task
  status stays independent of the label taxonomy.
- Codex session IDs are attached automatically to task comments when a
  Codex shell process exposes `CODEX_THREAD_ID` and invokes the managed
  `agent-backlog` CLI. See [Resume Codex sessions](#resume-codex-sessions)
  for the precise limits. No generic cross-provider one-click resume exists.
- Global AGENTS.md guidance requests task creation, deduplication and
  updates from agents with command access. It is **best-effort**; without
  runtime enforcement/hooks it does not guarantee that every turn is recorded.

## Resume Codex sessions

When a **local Codex shell tool** exposes `CODEX_THREAD_ID`, any successful
`agent-backlog task create` or `agent-backlog task edit` automatically records
the current Codex session on the affected task. No additional agent command is
required, and subsequent edits from the same session do not duplicate it.
Different Codex sessions can be attached to the same task independently.

Open the ticket with **Option-K** and copy the `codex resume` command from its
**Comments** section into a terminal. For example, a verified ticket comment
has this format (the UUID below is illustrative only):

```bash
codex resume 123e4567-e89b-42d3-a456-426614174000
```

The session is tied to the **Codex process that wrote the task**, not inferred
from repository, commit, PR, the focused app, or `session-find` suggestions.
`session-find` remains useful for retrospective discovery but is not the
source of identity for this feature. Without a valid `CODEX_THREAD_ID`, the
task write still succeeds but no session link is added. A failed task write
does not add a comment. A failed secondary session-link operation is reported
on stderr without falsely failing the already-saved task. Neither ChatGPT nor
Work session URLs are automatically linked in this version.

## Kanban columns

The same eight columns appear on both Mac profiles: `To Do`, `In Progress`,
`Pushed`, `PR`, `Merged`, `STG`, `PRD`, and `Done`. `PR` means
**merge-ready**, not merely an opened PR: CI must pass, blocking review
threads must be resolved, and required approvals must be present. `Pushed`
contains remote changes that are not yet merge-ready.

Both rollout stages group **deployment and optional validation**. In a
private Dotfiles workflow, `STG` means applying the configuration on the
private Mac; `PRD` means deployment on the professional Mac, confirmed by the
user. Behavioral acceptance can happen at either point or be skipped; it is
tracked independently. The agent on the private Mac must not inspect the
professional Mac. For actual company projects, `STG` and `PRD` correspond
to the real staging and production environments. The machine-specific
interpretation is agent guidance, **not a column name**. `Done` requires
final acceptance, not merely a merge or rollout.

## Optional confirmation labels

Two visible checkmark labels are available on task cards at **any stage**:

- `✅ Reviewed` — you personally inspected the code or diff in VS Code.
- `✅ Behavior tested` — you exercised the functionality and confirmed it
  behaves as intended (automated unit/CI tests do not count).

Absence means **not yet confirmed**, not failed. You may skip both: neither
blocks pushing, PR readiness, merge, deployment or completion. Agents must
not infer a checkmark from successful CI, a push, a merge or their own tests.
They only add it after your explicit confirmation. Clear a label if later
code changes invalidate that earlier approval.

To update a task manually while keeping its existing labels:

```bash
agent-backlog task edit AGENT-1 --add-label "✅ Reviewed"
agent-backlog task edit AGENT-1 --add-label "✅ Behavior tested"
agent-backlog task edit AGENT-1 --remove-label "✅ Behavior tested"
```

`chezmoi apply` manages the workflow columns and the available label choices
while preserving all existing task files and user labels. This does not
implement agent-specific hooks or automated observation of user actions.

## Deployment and troubleshooting

A normal `chezmoi apply` installs the shell wrapper, Hammerspoon module,
LaunchAgent and agent guidance. The wrapper initializes a filesystem-only
Backlog.md project on first invocation with `AGENT-` task IDs; no manual
`backlog init` or Git initialization is needed.

To inspect the running service:

```bash
launchctl print "gui/$(id -u)/com.arthur.agent-backlog"
curl --fail --silent --output /dev/null http://127.0.0.1:6420
```

The service logs go to `~/Library/Logs/agent-backlog.log` and
`~/Library/Logs/agent-backlog.err.log`.

The task store is **per Mac**, deliberately outside Git, and is not synced
between Macs or backed up by Dotfiles. If cross-Mac synchronization becomes
necessary, design a separate encrypted/private data synchronization policy.
Do not point the wrapper at an arbitrary Git worktree.

For safe experiments, set `AGENT_BACKLOG_DIR` to a temporary directory.
The LaunchAgent intentionally uses the default directory and does not read
an alternative path. No Codex-specific or other provider-specific hooks are
installed by this prototype.
