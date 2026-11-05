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

The same nine columns appear on both Mac profiles: `To Do`, `In Progress`,
`Local Review`, `Pushed`, `PR`, `Merged`, `STG`, `PRD`, and `Done`. `PR` means
**merge-ready**, not merely an opened PR: CI must pass, blocking review
threads must be resolved, and required approvals must be present. `Pushed`
contains remote changes that are not yet merge-ready.

Both rollout stages combine **deployment and validation**. In a private
Dotfiles workflow, `STG` is applying and validating the configuration on the
private Mac; `PRD` is the corresponding rollout and user-confirmed validation
on the professional Mac. The agent on the private Mac must not inspect the
professional Mac. For actual company projects, `STG` and `PRD` correspond
to the real staging and production environments. The machine-specific
interpretation is agent guidance, **not a column name**. `Done` requires
final acceptance, not merely a merge or rollout.

`chezmoi apply` manages the workflow-column configuration while preserving
all existing task files. This does not implement agent-specific hooks or
automatic observation of manual reviews/deployments.

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
