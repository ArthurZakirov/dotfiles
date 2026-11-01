<a id="source-code-snippets"></a>
# 🧾 Source code snippets and proposed changes

When describing inspected code, quote the relevant source. Let the excerpt establish **what** exists; use surrounding prose to explain **why** it matters or **what follows**.

## Give every source excerpt two locations

- **Above the fence:** a verified, clickable link identifying the file and relevant line numbers.
- **Inside the fence:** the exact source-relative path as the first line, written as a comment that survives copying.

Use a real language tag. If the source location is not verifiable, provide its exact known locator and state that the link is unresolved.

## Preserve the enclosing structure

Keep the relevant lines and their real enclosing structure. Each omitted span is marked with the source language's comment syntax.

- **Python:** include the actual `def` line; for a method, also include the enclosing `class` line. Mark omitted spans with `# ...`.
- **Markdown:** include the heading under which the quoted content appears. Use `<!-- ... -->` for omissions if quoting literal Markdown.
- **YAML:** include the enclosing parent keys. Use `# ...` for omissions and the path comment.
- **JSON:** include the enclosing object keys. For an annotated excerpt with `//` comments, use a `jsonc` fence rather than `json`.
- **SQL:** include the `SELECT` statement or CTE name. Use `-- ...` for omissions and the path comment.
- **Other languages:** show the nearest real enclosing declaration, using that language's comment syntax.

## Compare code changes

- **BEFORE:** show the original relevant lines, including enclosing scope and both source locations.
- **AFTER:** show the same relevant lines with the proposed or applied modification. Label proposed code as proposed.
- **Within a longer AFTER excerpt:** mark added lines `# NEW` and replacements `# CHANGED` (or the language's comment equivalent). Place each replaced old line in a comment immediately above the new line. Leave unchanged lines unmarked. These annotations illustrate a change; they are not production code.

## Match the excerpt to the reader's purpose

- **Explaining existing behavior:** show the actual lines instead of referring vaguely to a handler or field.
- **Quoting Markdown wording:** use a blockquote or concise paraphrase plus a link when the text's meaning matters. Use a `markdown` fence with its heading when its syntax matters.
- **Providing runnable commands:** use an executable `sh` or `bash` fence with appropriate arguments. Standalone commands do not need fictitious source file comments or containing function declarations.
