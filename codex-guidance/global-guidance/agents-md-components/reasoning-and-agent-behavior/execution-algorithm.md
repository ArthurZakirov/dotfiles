<a id="execution-algorithm"></a>
# 🧭 Transparent execution algorithm

| When | Then |
| --- | --- |
| A task requires multiple reads, comparisons, transformations, or writes across files, tools, skills, or data sources. | Before making substantive changes, explain the operational sequence in natural language: **inputs to read → comparisons and decision criteria → intended writes → validation**. Name concrete files, properties, skills, and relevant references when known. Keep it concise enough for human review. |
| Applying one or more skills. | Identify the skill entrypoints and relevant reference files to be loaded; explain how their applicable rules will be checked against the target artifacts. Distinguish discovered violations from general aspirations. |
| New evidence changes the planned sequence or reveals a blocker. | Update the user with the material deviation, actual scope, and revised next operation; do not silently continue under an obsolete plan. |
| Handing over results. | Distinguish what was read, compared, changed, and verified from what was merely planned. State coverage and remaining gaps; never claim complete compliance without checking the final artifacts. |
| A task is trivial or the sequence would add no decision-relevant information. | Perform it directly without manufacturing a multi-step plan. |

This is an operational description of externally observable work, **not** a request to reveal private reasoning. Do not confuse reading a skill with having applied its rules.
