<a id="agent-behavior-lifecycle"></a>
# 🧭 Agent behavior lifecycle

| When | Then |
| --- | --- |
| The user expresses a new wish for how the agent, computer setup, workflow, or broader system should behave, but the behavior has not yet been operationalized. | Treat it as problem-space intent, not as an implemented instruction. Capture or merge it into `global-guidance/wishlist/` instead of copying the prose into production `AGENTS.md`, skills, hooks, or other runtime guidance. |
| A wishlist item is selected for implementation. | Use `engineer-agentic-ai` to identify observable signals, trigger, decision rule, actuator, persistence, reliability needs, implementation surface, and verification. Preserve the original desired outcome while translating it into mechanisms. |
| The mechanism has been implemented and validated. | Obtain the required human review, then promote only the validated rule or mechanism into the appropriate canonical production surface. Remove or mark the wishlist item as promoted so the wishlist does not become a second active source of truth. |
| A desired behavior is already operationalized and verified. | Store only the compact routing condition or invariant on always-loaded surfaces; keep substantial detail in the narrowest appropriate reference, skill, hook, tool, validator, script, or automation. |
