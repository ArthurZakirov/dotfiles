<a id="information-presentation"></a>
# 🧠 Information presentation

Before sending a user-facing reply (including a progress update) or saving a human-readable artifact, inspect its actual draft:

1. **Scan enumerations.** Convert three or more independently scannable items into a lead-in and individual bullets.
2. **Inspect groups.** Separate inventories from rules or other different types of information. Check that each heading and list lead-in describes its immediate children.
3. **Inspect code claims.** If the draft discusses repository code, compare identifiers, expressions, and described effects with the inspected source. Correct mismatches.
4. **Inspect references.** For each located file or symbol, verify the link destination against the relevant checkout. Replace unverified links with the known exact locator and an explicit limitation.
5. **Inspect the rendered output.** Fix long table cells, detached examples, broken Markdown, and dense paragraphs before handoff.

Use the child sections for the exact edits required by each check. Preserve machine-readable formats, exact quotations, and user-requested layouts.

When editing an artifact used by software and human readers, run its parser or generator checks, then inspect the resulting Markdown for readable headings, lists, and links. Keep the format required by the software.

When creating, editing, or reviewing a Markdown file, search for and load `format-markdown` before editing. Use its Markdown checks on the finished file. For a substantial information-architecture change, also search for and load `information-representation-design` before deciding how to restructure the content.
