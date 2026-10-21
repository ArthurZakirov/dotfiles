<a id="unresolved-implementation-decisions"></a>
# 🧩 Unresolved implementation decisions

| When | Then |
| --- | --- |
| A change depends on unanswered requirements, domain rules, interface contracts, or stakeholder decisions. | Resolve material uncertainty **before implementing dependent behavior**. Follow the steps below. |

1. **Assess and investigate.** Check available specifications, documentation, prior decisions and chats, code, tests, and other evidence. Resolve ordinary engineering choices from established conventions without manufacturing stakeholder approvals. If no material uncertainty remains, proceed normally.
2. **Surface the unresolved decision.** If a requirement or contract remains unclear, give the user the precise question and relevant evidence so **the user can consult the accountable person**. Do not contact stakeholders on the user's behalf.
3. **Handle pending work.** Do not guess, implement provisional behavior, or add speculative branches or abstractions to cover possible answers. Support multiple outcomes only when that flexibility is confirmed.
   - **If independent work remains:** Continue authorized work. Implement a confirmed subset only if independently useful and future additions are strictly additive without rework.
   - **Otherwise:** Tell the user the task is blocked. For team-managed work, suggest coordinating with the team to mark it blocked and pick up another task. Do not change ticket status or switch tasks without authorization.
