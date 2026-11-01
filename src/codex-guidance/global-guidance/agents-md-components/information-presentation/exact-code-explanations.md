<a id="exact-code-explanations"></a>
# 🔎 Exact explanations of code

When explaining existing code, identify the **actual function, expression, variable, column, value, or output** instead of describing an imagined object or relationship.

| When | Then |
| --- | --- |
| Explaining what code does. | Name the executable expression or function and the exact affected rows, fields, or values. Avoid metaphors such as `left edge`, `both halves`, `tail`, `envelope`, `owns`, `carries`, or `is responsible for` unless quoting an actual identifier. |
| Explaining a code change. | Show a concrete input → output example with actual values when available. For a bug, state the failing input, observed incorrect output, and expected output. Mark hypothetical examples explicitly. |
| Using abstract terminology about the code. | Replace words such as `partition`, `disjoint`, `invariant`, `idempotent`, `boundary`, and `semantics` with the relevant expression, variable, function, or value. Keep such a word only when it is an actual code identifier or is indispensable to a directly cited external specification. |
| Explaining a condition or interval. | Write the expression, e.g. `state_date < rebuild_start`, and state which rows satisfy it and what the code writes for those rows. |

**Not:** "Days before the rebuild start now have an owner."

**Write:** "Rows with `state_date < rebuild_start` are now written by `_keep_intervals_before_rebuild`."

**Not:** "The kept prefix carries `is_current=False`."

**Write:** "Those rows get `is_current=False`; no row has `is_current=True` unless the rebuild writes one."

**Not:** "The old left edge is wrong."

**Write:** "The explode starts at `valid_from`; it must start at `rebuild_start`."
