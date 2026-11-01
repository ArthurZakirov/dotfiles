<a id="exact-code-explanations"></a>
# 🔎 Exact explanations and navigation of code

Apply these rules to any question or explanation involving repository code, from locating an implementation through diagnosing or modifying it. The user's wording does not limit their applicability.

The examples below are hypothetical illustrations, not observations from the current checkout.

## Preserve exact source identifiers

When naming inspected code, reproduce **every character exactly as it appears in the source**. Use inline code backticks for literals; when a verified symbol link is available, use a plain-text link label and retain the exact symbol at its destination.

- **Bad:** "the underscore keep intervals before rebuild function."
- **Good:** `_keep_intervals_before_rebuild`.

## Describe the actual operation and values

Explain code by pointing to the relevant source expression and what it actually does. Vague metaphors such as "left edge" or "owns" and abstract terms such as "partition" or "idempotent" cause the same problem when they replace the concrete operation. Use technical terms when they clarify an already identified mechanism.

**Example — which rows are processed**

- **Bad:** "The left-edge partition owns the earlier days."
- **Good:** "Rows satisfying `state_date < rebuild_start` are passed to `_keep_intervals_before_rebuild`."

**Example — what a condition changes**

- **Bad:** "The older dates are kept."
- **Good:** "For `state_date < rebuild_start` the existing rows are kept; rows with `state_date >= rebuild_start` are rebuilt."

**Example — why an output is incorrect**

- **Bad:** "The old left edge is wrong."
- **Good (hypothetical):** "With `valid_from='2026-10-01'` and `rebuild_start='2026-10-10'`, the output starts at `2026-10-01`; the expected start is `2026-10-10`."

Verify claims about real behavior against the source or observed output. Show representative inputs, values, or resulting outputs when they make an otherwise abstract behavior easier to understand; identify constructed examples as hypothetical. For inspected code, provide the relevant scoped excerpt as specified under Source code snippets.
