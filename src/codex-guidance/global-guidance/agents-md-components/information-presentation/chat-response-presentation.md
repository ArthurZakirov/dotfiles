<a id="chat-response-presentation"></a>
# 💬 Chat response presentation

Chat-specific visual conventions belong here. Apply [🧩 Information representation design](#information-representation-design) to the substance and layout of **every user-visible chat message**; its four stages and rules are not reserved for final replies. Keep medium-independent design rules in their canonical component.

| When | Then |
| --- | --- |
| Composing **any user-visible chat message**—including intermediate work-in-progress updates, partial findings, blockers, corrections, and the final answer. | **Before sending each message**, apply the four stages and relevant rules in [🧩 Information representation design](#information-representation-design). Identify what the message communicates, make peer items semantically coherent, and choose a representation proportional to its content. The rules apply to the **accumulating sequence of messages**, not just to each message in isolation. |
| Reporting **any intermediate progress update**, even one sentence long. | Start with `🟡` followed by a **short, descriptive bold title or heading** (typically two to four words) that identifies the subject or outcome, then give the update. For example: `🟡 **Repository inspected.**`, `🟡 **Guidance integrated.**`, `🟡 **Validation pending.**`. Use specific, consistent terminology so readers can scan a long sequence of small updates. Do **not** omit this title because an individual message is short; do **not** inflate a short update into a table or a long structured report. |
| A user turn requires multiple substantive steps, tool calls, or meaningful work before the result is ready. | Report meaningful milestones, findings, blockers, or next steps rather than one sentence for every command or internal step. Keep the updates concise, but preserve the **titled** format of each update so the conversation remains navigable as it accumulates. |
| Implementation and applicable local validation are complete, and the commit and push have succeeded. | Before starting any CI/CD query, polling, or blocking wait, send a concise `🟡` progress update saying the change is implemented and available for review, linking the PR, pushed commit, or branch diff. State that remote checks are pending or not yet checked and that you are checking them automatically. Continue monitoring under the Git workflow without ending the turn or asking the user to prompt again. Review readiness does not mean CI has passed or the task is complete. |
| The requested work for the turn is complete and control is being handed back to the user. | Send one final response that begins with `🟢`. Make it self-contained: summarize the result, what changed, what was verified, and any remaining blocker or user decision so the user does not need to read the preceding `🟡` updates. |
| Sending the final response after creating, editing, moving, renaming, or deleting any file in a Git repository or linked worktree, regardless of staging, commits, or pushes. | Follow the **Checkout review output format** below for every affected checkout. The `bash` fence must contain **exactly one line: the raw absolute checkout directory path**, and nothing else: no branch, variable assignment, `cd`, `code` command, quotes, comments, labels, or other text. Put the branch on a **separate line outside the code fence**, so copying the code block yields only the path for VS Code's Go to Folder dialog. Get the path from `git rev-parse --show-toplevel` in that checkout (not the shared Git directory); record the branch at edit time with `git branch --show-current`. If HEAD is detached, report `detached HEAD` and the commit separately instead of inventing a branch. Report the branch used for the edits even if the checkout later switches branches. Repeat the format independently for each edited checkout, whether or not edits were committed or pushed. |
| The turn is simple enough to answer directly without meaningful intermediate work. | Skip `🟡` progress updates and give the result directly; use `🟢` only when it helps distinguish a completed multi-step handoff. |

### 📁 Checkout review output format

After file edits, use this format for each edited checkout, substituting verified values. Keep the **path-only** `bash` fence separate from the branch:

**Checkout path (copy for VS Code):**

```bash
/Users/example/Repos/project.worktrees/feat-example
```

**Branch:** `feat/example`

