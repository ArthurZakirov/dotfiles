<a id="anchoring-reader-never-searches"></a>
# 🔗 Anchoring: the reader never goes searching

When an agent references a concrete thing, the reader should either see the relevant thing inline or be able to reach its source directly. Do not make the reader manually hunt for files, symbols, tickets, commits, tables, pages, or other referenced artifacts.

| When | Then |
| --- | --- |
| Referring to an existing artifact, object, source, or location that can be resolved. | Make the reference directly reachable with a meaningful link, citation, native mention, or equivalent surface-appropriate anchor. Prefer labels that name the thing rather than generic text such as `here`. |
| The referenced content is small enough that seeing it inline materially improves comprehension. | Show the relevant excerpt, snippet, value, image, or other artifact inline and anchor it to its source when one exists. Do not add a prose description that forces the reader to go inspect the source to understand the point. |
| A link or anchor cannot be produced reliably because the target is unavailable, unresolved, or does not exist yet. | Say that briefly and provide the next-best concrete locator, such as the exact file, symbol, command, query, or destination where the proposed content would live. Do not invent a link. |
| Before handing information-bearing output to a reader. | Check whether anything referenced would require the reader to search for it. If so, provide the thing inline or add a direct, meaningful anchor to its source. |
| A more specific repository, platform, or medium rule defines how an anchor must be constructed. | Follow that local rule for the anchor shape; keep this global rule concerned with the invariant that referenced things remain directly discoverable. |
