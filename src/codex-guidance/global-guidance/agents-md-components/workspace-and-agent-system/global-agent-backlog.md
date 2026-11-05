<a id="global-agent-backlog"></a>
# 📋 Mac-wide agent work tracking

| When | Then |
| --- | --- |
| Starting or resuming actionable user work, including bugs and improvement requests across repositories or voice conversations. | If local shell access and the `agent-backlog` command are available, inspect the Mac-wide tasks and create or update the matching task rather than relying on chat history. Read [global backlog workflow](agents-md-references/global-agent-backlog.md) before using the CLI. Do not create a duplicate for a follow-up question. |
| Material progress, a requirement change, a blocker, a test result, a commit, or a PR changes an active task's state. | Update the same Backlog.md task with a brief status or comment and navigable evidence. Only mark a task Done when its requirements are verified; do not treat a commit as proof of correctness. |
| A verifiable agent session identifier or chat permalink is available. | Store it on the task with the agent/tool name and, when supported, an exact resume link or command. Never infer a missing session ID. |
| The runtime has no authorized shell access or Backlog.md is unavailable. | State that the board was not updated. Do not claim that AGENTS.md alone guarantees persistence or that hooks are installed. |
