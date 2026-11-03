# Codex Scope & Effort checkpoint

An optional Codex hook records a scope/effort decision **per turn and workspace**
before a potentially mutating tool call. It replaces the blanket guidance-audit
footer. It does not determine whether the agent's scope judgment is correct.

## Enable on the target machine

After the branch has been reviewed, merged, installed with chezmoi, and Codex
has loaded the new hooks, run:

```bash
python3 "$HOME/.codex/hooks-json/scope-checkpoint/checkpoint.py" enable
python3 "$HOME/.codex/hooks-json/scope-checkpoint/checkpoint.py" status
```

Start a **new Codex chat** to verify hook registration and global guidance.
The script is installed for all profiles but **disabled by default** on each
machine. Enabling it changes only the local Codex home; no assessment is
committed to Git.

To stop blocking tool calls:

```bash
python3 "$HOME/.codex/hooks-json/scope-checkpoint/checkpoint.py" disable
```

## Expected behavior

When enabled, `UserPromptSubmit` supplies session/turn identifiers
and an instruction to evaluate shared-work changes. Before editing, Codex
should give the user a compact **Scope & Effort** outcome, including justified
**in-scope** verdicts.

A corresponding assessment is stored with the local recorder. It includes the
ticket baseline, proposed change and source, classification (`explicit`,
`routine`, `necessary`, `disputed`, `expansion`, or `unknown`),
evidence/reason, human effort, remaining budget or explicit unknown, and
the decision (`proceed` or `pause`).

`PreToolUse` denies supported potentially mutating calls until a `proceed`
record exists for that session, turn, and workspace. Read-only tools can
proceed. A `pause` assessment denies writes; unresolved requirements and
missing accepted scope cannot be recorded as `proceed`. The next user turn
requires a new assessment. Reassess after materially expanding the plan.

Work cannot resume on disputed scope merely because the requester repeats the
request. Resolve the ticket-level decision via the established team process.

## Limitations

- This is a **workflow guardrail**, not a security boundary. Hook callbacks
  can fail open, some tool paths are not intercepted, and a shell command can
  hide writes. The read-only classifier is conservative: an unfamiliar command
  may be stopped even when harmless. Existing interactive processes might
  mutate without another `PreToolUse`.
- The gate verifies that an assessment was *recorded*; it cannot independently
  verify its semantic correctness, ticket consultation, or the user-visible
  delivery of the message.
- One record is scoped to a turn and workspace, not every edit inside a turn.
- Missing accepted scope requires clarification; do not invent budgets.
- Assessments stay **local** in `$CODEX_HOME/scope-checkpoint/records/`
  (or `~/.codex/scope-checkpoint/records/`), with private file permissions.
  They may contain workplace metadata; never commit or upload them.

## Workplace verification

Use a fresh chat and a representative ticket with acceptance criteria.

1. Request a focused regression test. Expect a visible **in-scope** assessment
   before the first write.
2. Request an unrelated E2E framework. Expect a reasoned **pause** before edits.
3. Request significant effort without ticket scope or a reliable budget.
   Expect an explicit evidence gap and pause on the affected work.
4. Check that `UserPromptSubmit` and `PreToolUse` actually ran; verify
   denial without a record, acceptance with an eligible record, and a
   new requirement after the next user turn.
5. Test Codex CLI and Codex Desktop separately; their hook coverage cannot
   be assumed identical.

A successful rendering or file-presence check is not proof of correct agent
behavior or user-visible communication.
