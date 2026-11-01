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
| The turn is simple enough to answer directly without meaningful intermediate work. | Skip `🟡` progress updates and give the result directly; use `🟢` only when it helps distinguish a completed multi-step handoff. |

## Guidance and Skill Transparency

**Every user-facing reply** has two parts, in this order:

1. **Answer / update:** Address the user's actual request normally.
2. **🧾 Guidance audit:** Append a compact, separately labeled account of which instructions and skills were genuinely encountered and applied.

In the guidance audit, report:

| Field | What to report |
| --- | --- |
| **Read** | Relevant `AGENTS.md` sections, `SKILL.md` entrypoints, and reference files actually read or available in the effective context. Distinguish a file read *this turn* from guidance retained from an earlier turn. Say `none` when nothing new was read; do not equate discovered skill metadata with reading its body. |
| **Applied** | The specific applicable rule and an observable action, decision, or artifact showing its application. State `not applicable` for relevant rules whose trigger did not match; do not imply that reading a rule proves it was followed. |
| **Gaps** | Materially relevant guidance, evidence, or checks that could not be loaded or verified, and why. Omit this field when there are no material gaps. |

Keep the substantive answer first, even for short replies. A flagged risk should appear **before** affected implementation, not solely in a post-hoc audit.
