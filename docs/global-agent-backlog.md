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
- Agent sessions belong in concise task comments or references. Record the
  actual agent, session identifier, and exact resume command/permalink when
  one is available. There is no universal cross-agent one-click resume API.
- Global AGENTS.md guidance requests task creation, deduplication and
  updates from agents with command access. It is **best-effort**; without
  runtime enforcement/hooks it does not guarantee that every turn is recorded.

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
