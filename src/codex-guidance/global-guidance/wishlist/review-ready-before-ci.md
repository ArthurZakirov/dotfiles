# 🔔 Announce review readiness before waiting for CI

Status: selected for implementation; candidate rule awaiting behavioral validation and human review. This wishlist entry is not active runtime guidance.

## 🎯 Desired outcome

After implementing, validating locally, committing, and pushing a change, the agent tells the user immediately that it is ready for review. It continues checking CI/CD automatically without waiting for another prompt. The user can review while GitHub Actions or Bitbucket Pipelines runs, rather than hearing nothing until the pipeline finishes.

## 🛠️ Proposed mechanism

The existing [Git workflow](../agents-md-components/workspace-and-agent-system/git-workflow.md) already requires monitoring remote checks after pushing. Add the following row to [Chat response presentation](../agents-md-components/information-presentation/chat-response-presentation.md), alongside the in-progress update rule. Keep pipeline handling in the Git workflow so there is one owner for that behavior.

| When | Then |
| --- | --- |
| Implementation and applicable local validation are complete, and the commit and push have succeeded. | Before starting any CI/CD polling or blocking wait, send a concise `🟡` progress update saying the change is implemented and available for review, linking the PR, pushed commit, or branch diff. State that remote checks are pending or not yet checked and that you are checking them automatically. Continue monitoring under the Git workflow without ending the turn or asking the user to prompt again. Review readiness does not mean CI has passed or the task is complete. |

Example: “🟡 Implemented and pushed: [review the change](https://example.com/review). Local checks passed. You can review now; I’m checking CI/CD.” The example URL is a placeholder; actual updates must link the real review target.

## 🔗 Operationalization

| Link | Mechanism |
| --- | --- |
| Signal and sensor | Agent-visible implementation, local validation, commit, and successful push results. |
| Trigger | Successful push of a locally validated implementation, before the first remote-check query or wait. |
| Decision | Announce review readiness only when all prerequisites hold; failed validation or push gets an accurate blocker update. |
| Actuator | In-progress chat message followed by structured CI queries for the pushed revision. |
| Persistence | Canonical chat component, rendered into managed global guidance after validation and review. Keep the pushed revision and latest CI state in task context. |
| Reliability | Required at every qualifying handoff, including a new qualifying push after fixing CI; instruction compliance is model-mediated, not a deterministic delivery guarantee. |
| Verification | Observe message ordering and continued tool execution in representative agent runs, rather than checking only generated text. |

## 🧪 Acceptance and promotion

Exercise these cases on the target agent surface before promotion:

1. Successful push with slow CI: a real review link and pending-status message appear before the first CI query/wait; the agent continues monitoring in the same turn.
2. Repeat the qualifying case to check consistency. A later successful CI result produces a final handoff with the actual result.
3. Failed CI: the early review message remains accurate; the agent investigates, fixes within scope, validates, pushes, announces the new reviewable revision, and monitors again.
4. Failed local validation or push: no claim that the implementation is pushed and ready for review.
5. No checks yet, inaccessible CI, or no configured pipeline: report the observed state precisely; never claim green checks without evidence.
6. GitHub and Bitbucket: preserve the same message ordering using the available structured integration for each provider. Do not infer Bitbucket coverage from a GitHub-only run.

Static validation can confirm Markdown, links, and unchanged generated guidance; it cannot establish runtime compliance. No representative runtime evidence has been recorded yet.

After behavioral validation, obtain human review of this exact rule. Then insert it into the canonical chat component, render with `python3 src/codex-guidance/render.py`, inspect the generated diff, validate it, and apply through the documented chezmoi workflow. Mark this entry promoted so it cannot become a second active source of truth.
