<a id="information-representation-design"></a>
# 🧩 Representation

| When | Then |
| --- | --- |
| Choosing how to express the information. | Choose the representation that makes the important relationship easiest to perceive: use tables for repeated records with shared fields, numbered lists for ordered sequences, bullets for unordered independent points, hierarchy for parent/child concepts, prose for narrative or causal reasoning, and diagrams/charts when relationships or quantitative patterns are materially clearer visually. |
| Several rules or records repeat the same labels or schema. | Encode the shared schema once, usually as columns in a table, rather than repeating headings such as `When` / `Then` for every item. |
| The information is a simple linear procedure. | Keep it as a numbered list rather than forcing it into a table. |
| A sentence enumerates three or more distinct items that readers may scan individually. | End the lead-in with `:` and put **each distinct item on its own bullet**. Do not merge several independent inventory items into one bullet just to shorten the list. Keep inseparable pairs such as `staged versus unstaged changes` together. |
| A paragraph mixes an inventory with separate rules, exceptions, or consequences. | Put the inventory under its own lead-in and bullets. Then use a second lead-in such as `The following rules apply:` with **one bullet per independent rule**. Do not pack unrelated rules into one paragraph or append them as more inventory bullets. |
| A new sentence introduces a different point, action, or reason. | Start a new paragraph or bullet instead of appending it to a dense block. Keep connected causal explanations as prose; do not mechanically force every sentence onto its own line. |

**Example: an inventory and separate rules must produce two bulleted groups, not a list followed by a run-on paragraph.**

The updater preserves:

- staged versus unstaged changes
- untracked and ignored files
- symlinks
- executable modes
- conflicted indexes
- previous commits

The following rules apply:

- Submodule copies receive independent Git metadata.
- Interrupted-operation metadata is saved as evidence.
- Archived operations are not automatically resumed in recovery copies.

After drafting a list or paragraph, compare it with the `When` cases above. Rewrite remaining chained inventories and mixed rule groups before sending or saving.
