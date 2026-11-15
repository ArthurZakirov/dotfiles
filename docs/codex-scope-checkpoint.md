# Codex Scope & Effort checkpoint

An optional Codex hook records a scope/effort decision **per turn and workspace**
before a potentially mutating tool call. It replaces the blanket guidance-audit
footer. It does not determine whether the agent's scope judgment is correct.

## Enable manually

A normal `chezmoi apply` removes the checkpoint registrations from the managed
`~/.codex/hooks.json` and removes the old installed `checkpoint.py`. Existing
assessment records stay in place.

To enable the checkpoint until the next apply, run these commands from the
Dotfiles repository root:

```sh
install -d "$HOME/.codex/hooks-json/scope-checkpoint"
install -m 755 src/codex-guidance/scope-checkpoint/checkpoint.py \
  "$HOME/.codex/hooks-json/scope-checkpoint/checkpoint.py"
```

In `~/.codex/hooks.json`, append the following handler to the existing
`UserPromptSubmit` group's `hooks` array. Add a `PreToolUse` event with a group
whose `hooks` array contains the same handler. Replace `/absolute/home` with
your home directory.

```json
{
  "type": "command",
  "command": "python3 \"/absolute/home/.codex/hooks-json/scope-checkpoint/checkpoint.py\" hook",
  "timeoutSec": 5,
  "async": false
}
```

Start a new Codex session to load the configuration. Use Codex's native hook
settings to enable both handlers if prompted. To restore the managed default,
run `chezmoi apply --force` for the two affected paths:

```sh
chezmoi apply --force "$HOME/.codex/hooks.json" \
  "$HOME/.codex/hooks-json/scope-checkpoint/checkpoint.py"
```

Without `--force`, confirm the Chezmoi prompt if it detects edits to the managed
hook configuration.

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
