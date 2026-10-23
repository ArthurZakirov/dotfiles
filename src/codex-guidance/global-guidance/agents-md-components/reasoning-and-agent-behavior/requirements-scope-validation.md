<a id="requirements-scope-validation"></a>
# 🎯 Requirements and scope validation

| When | Then |
| --- | --- |
| **Before implementing company or other shared work:** The agent is about to create or modify behavior, tests, configuration, or another deliverable under an agreed or externally governed scope, whether requested by the user or initiated by the agent. | Read and apply the [requirements and scope validation procedure](agents-md-references/requirements-scope-validation.md) **before implementation**. Evaluate the accepted outcome against the proposed change, including plausible unapproved additions; do not silently assume uncertain work is in scope. |
| **While working on a personal project whose scope the user alone controls:** The proposed solution adds independently useful behavior, broad refactoring, unexpected review cost, or work not clearly requested. | Briefly flag **possible scope growth** and its concrete basis before doing the extra work. The owner may authorize it directly; do not impose the company-ticket approval procedure on personal projects. |
| **When evidence for or against scope expansion is incomplete:** A new requirement, fallback, test suite, or infrastructure change might exceed the agreed outcome, but the baseline or necessity is unclear. | Prefer an early **possible scope creep** warning over a silent false negative. Distinguish a tentative flag from confirmed expansion; obtain missing evidence or a scope decision before implementing the disputed portion, while continuing independent authorized work. |
