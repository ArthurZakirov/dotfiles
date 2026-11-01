<a id="anchoring-reader-never-searches"></a>
# 🔗 Anchoring: the reader never goes searching

When preparing a reference to an existing file, symbol, ticket, or document, locate its actual source first. Insert a verified link or concise excerpt next to the claim it supports. If the destination cannot be confirmed, state the known locator and the limitation.

| When | Then |
| --- | --- |
| Referring to an existing artifact, object, source, or location that can be resolved. | Make **every mention** directly reachable with a meaningful link, citation, native mention, or equivalent surface-appropriate anchor, including symbols, functions, variables, constants, columns, configuration keys, file paths, dotfiles, logs, and specs. Do not link only the first mention. |
| Naming a located file or symbol in a link. | Make the **visible label name the thing**; put the path and line anchor in the href. **Bad:** `[here](src/loader.py#L90)` or `[line 90](src/loader.py#L90)`. **Good:** `[loader.py:90](src/loader.py#L90)`; if a leading underscore breaks rendering, use `[read_snapshot](src/loader.py#L90)` and preserve the exact `_read_snapshot` identifier in nearby backticked code. Do not expose a long deep path as the label. |
| Rendering a Markdown link label. | Use **plain text**, not code backticks around the label. Never shorten a real identifier to make it look nicer: preserve exact case, words, and other characters. If a renderer breaks a link label beginning with `_` or `*`, omit that leading formatting-sensitive character **only in the visible label**; preserve the exact name in the href and use exact backticked spelling when needed for precise code identification. **Bad:** a label that exposes a raw href because `_` was parsed as formatting. **Good:** `[read_snapshot](src/loader.py#L90)` with the full `_read_snapshot` symbol retained at the destination. |
| The referenced content is small enough that seeing it inline materially improves comprehension. | Show the relevant excerpt, snippet, value, image, or other artifact inline **and** anchor it to its source when one exists. Surrounding prose should explain its significance, not make the reader search to learn what exists. |
| A link or anchor cannot be produced reliably because the target is unavailable, unresolved, or does not exist yet. | Say so briefly and provide the next-best exact locator: the file, identifier, command, query, or intended destination. Use backticks for unresolved literal code or paths instead of inventing hyperlinks. |
| Introducing a fact, rule, question, or example that will be referred to again later in the same explanation. | Give it a stable bold tag at its definition, such as **F1**, **R1**, or **Q1**; use that exact bold tag in every subsequent reference. Never say `the first fact` or `the previous rule` in its place. |
| Presenting verified repository code evidence to a user. | Read [code-evidence-and-vscode-navigation.md](agents-md-references/code-evidence-and-vscode-navigation.md) and open the correct file and line in VS Code when the environment supports it. |
| Before handing over text containing source links. | Verify the referenced path actually exists in the **correct repository/branch/worktree** and the claimed lines still refer to the intended content. Recheck rather than recycling stale line anchors. |
| A more specific repository, platform, or medium rule defines how an anchor must be constructed. | Follow that rule for the anchor shape while keeping references directly discoverable. |

**Choose the link base by the reader's destination:**

| Destination | Anchor |
| --- | --- |
| Chat with a local repository workspace | Relative to the session working directory, including a verified line anchor. |
| Markdown committed within the same repository | Relative to the **containing Markdown file's directory**, not the session working directory. Validate local file links, for example with `cd "$(dirname <file.md>)" && test -e <relative-target>`. |
| Markdown referring to a different repository | Use a Git-host URL to the **other repository** rather than a local relative path. Prefer a stable repository-level or landing-page anchor over a brittle file-and-line target if the repositories evolve independently. |
| PR description, external ticket, remote documentation, or remote message | An absolute URL that works without a local checkout. |

Use source-line links only when the destination can actually resolve them; do not pretend an uncommitted local change exists on the remote Git host.
