# Codex Scope & Effort checkpoint

An optional Codex hook records a scope/effort decision **per turn and workspace**
before a potentially mutating tool call. It replaces the blanket guidance-audit
footer. It does not determine whether the agent's scope judgment is correct.

## Configure using Codex hooks

After the branch is reviewed, merged, and installed with `chezmoi apply`,
start a **new Codex session** so Codex loads the updated hook registration.
Use Codex's native hook settings to enable or disable the scope-checkpoint
handlers under **`UserPromptSubmit`** and **`PreToolUse`**. Both need to be
enabled to get the initial reminder and the pre-write gate.

The managed hook has **no independent activation flag, enable/disable
command, or Python-script toggle**. When Codex calls the hook, the checkpoint
runs. Disabling the registered handlers in Codex stops those invocations.
There is no need to create or remove an `enabled` file. Existing legacy
`~/.codex/scope-checkpoint/enabled` files are ignored.

Assessment data remains local and is never committed to Git.

## Expected behavior

When invoked, `UserPromptSubmit` supplies session/turn identifiers
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
4. Toggle the native Codex hook settings for the two event handlers; verify
   that they invoke the checkpoint when enabled and do not invoke it when
   disabled. Check denial without a record, acceptance with an eligible
   record, and a new requirement after the next user turn.
5. Test Codex CLI and Codex Desktop separately; their hook coverage cannot
   be assumed identical.

A successful rendering or file-presence check is not proof of correct agent
behavior or user-visible communication.
