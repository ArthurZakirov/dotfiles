<a id="chat-response-presentation"></a>
# 💬 Chat response presentation

Chat-specific visual conventions belong here. Keep medium-independent relevance, anchoring, representation, and visual semantics under the `information-presentation` component group.

| When | Then |
| --- | --- |
| A user turn requires multiple substantive steps, tool calls, or meaningful work before the result is ready. | Use concise in-progress chat updates that begin with `🟡`. Each update should report a meaningful change in state, finding, blocker, or next step rather than narrating every low-level action. |
| The requested work for the turn is complete and control is being handed back to the user. | Send one final response that begins with `🟢`. Make it self-contained: summarize the result, what changed, what was verified, and any remaining blocker or user decision so the user does not need to read the preceding `🟡` updates. |
| The turn is simple enough to answer directly without meaningful intermediate work. | Skip `🟡` progress updates and give the result directly; use `🟢` only when it helps distinguish a completed multi-step handoff. |

## 🧪 One-day guidance transparency pilot

For the one-day evaluation period after this guidance is activated, **every user-facing reply** has two parts, in this order:

1. **Answer / update:** Address the user's actual request normally, including decisions, warnings, outcomes, and links. Do not bury an actionable scope warning in the audit.
2. **🧾 Guidance audit:** Append a compact, separately labeled account of which instructions and skills were genuinely encountered and applied. Keep it brief (normally two to four lines); add detail only when it matters for verification.

In the guidance audit, report:

| Field | What to report |
| --- | --- |
| **Read** | Relevant `AGENTS.md` sections, `SKILL.md` entrypoints, and reference files actually read or available in the effective context. Distinguish a file read *this turn* from guidance retained from an earlier turn. Say `none` when nothing new was read; do not equate discovered skill metadata with reading its body. |
| **Applied** | The specific applicable rule and an observable action, decision, or artifact showing its application. State `not applicable` for relevant rules whose trigger did not match; do not imply that reading a rule proves it was followed. |
| **Scope / effort** | One of: `not applicable`, `no concern observed` (with a concrete basis), `possible scope/effort concern` (with the evidence or uncertainty), or `blocked` (with the reason and required decision). Flag uncertain risks explicitly rather than silently clearing them. |
| **Gaps** | Materially relevant guidance, evidence, or checks that could not be loaded or verified, and why. Omit this field when there are no material gaps. |

Report an *observable compliance summary*, not private chain-of-thought, invented internal steps, or an exhaustive transcript. If the user requests a deeper explanation, provide sources, decisions, and observable evidence. Never invent a tool call, file read, validation, or compliance result.

Keep the substantive answer first, even for short replies. A flagged risk should appear **before** affected implementation, not solely in a post-hoc audit. This is a **manual one-day trial**, not an automatic expiry mechanism: the repository owner reviews the results after the trial and explicitly keeps, revises, or reverts the guidance.
