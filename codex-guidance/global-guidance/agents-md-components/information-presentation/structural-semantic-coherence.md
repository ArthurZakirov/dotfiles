<a id="structural-semantic-coherence"></a>
# 🧱 Structural and semantic coherence

When modifying an existing artifact, identify the **organizing principle of each affected group** before adding a sibling element. A group may be a directory of files, a section of headings, a sequence of workflow steps, a list of bullets, a collection of tests, a table of records, or a navigation hierarchy. Its peer elements should share a coherent **semantic role and level of abstraction** relative to that group's purpose. In an ordered workflow, peer steps represent successive stages; conditional outcomes belong within their owning step.

**Placement rule:** Determine what existing peers have in common, what each peer represents, and where the information is already handled. Then decide whether the new information belongs **inside an existing element**, **as a new peer at the appropriate position**, or **in a separate group or parent**. Do not append an item or create a new file merely because it is convenient. Do not elevate a detail to the rank of its container, or mix a rule's subject matter with its applicability/scope as if they were instances of the same category.

| Existing organization | Incoherent addition | Coherent integration |
| --- | --- | --- |
| Markdown headings each represent a step in an ordered workflow. | Append an unnumbered, explanatory heading as another step-level sibling. | Incorporate the information into the relevant step, or introduce a correctly positioned step if it is a separate action. |
| Each BDD `.feature` file owns the scenarios for one domain object. | Create a peer feature file for one scenario of an existing object. | Add the scenario to that object's feature file. |
| A bullet list enumerates coding-style dimensions such as typing, formatting, and naming. | Add `new functions only` as another dimension, although it describes scope. | State the applicability rule separately; retain only style dimensions as list peers. |
| A test directory groups files by module or component. | Create a new top-level file for a single regression case of an already covered component. | Put the test in the existing component's test file, unless it warrants a distinct test category. |
| A code directory groups handlers by domain resource. | Create an action-specific file as a peer of resource-specific modules without architectural justification. | Extend the appropriate resource module, or deliberately revise the overall organization. |
| A table has one row per invoice line item. | Insert an invoice grand total as though it were another line item. | Put the aggregate in a summary/footer, preserving the row schema. |
| Top-level navigation entries represent product areas. | Put a sub-feature page beside those product areas. | Nest the page under its owning area, unless it genuinely constitutes a new area. |

These examples illustrate the **same cross-medium principle**, not special-case rules. Diverse elements may coexist when the group's actual organizing criterion supports them; do not enforce superficial uniformity or preserve an unsuitable structure merely because it already exists. Respect explicit requirements for a different organization.
