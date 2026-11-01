<a id="source-code-snippets"></a>
# 🧾 Source code snippets and proposed changes

Use these rules when quoting **inspected file contents** in any user-facing text or human-readable artifact. Do not confuse source quotations with independent executable commands supplied for the reader to run.

| When | Then |
| --- | --- |
| Describing existing code, a handler, a field, a config value, or the implementation of a behavior. | **Show the relevant source lines** when available. The excerpt establishes **what** exists; surrounding prose explains **why** it matters or **what follows**. Do not replace an available source excerpt with a vague claim such as "the handler does X" or "there's a column for that." |
| Publishing a source-code fence. | Put a verified clickable **file-and-line link immediately above** the fence. Put the exact source-relative path as a comment on the **first line inside** the fence so the location survives copying. This is two locations with different purposes, not duplicate prose. If a link cannot be verified, state that and use a concrete path/locator instead of inventing an href. |
| Quoting a function or method. | Include its enclosing **exact** `def` line and, for a method, the enclosing `class` line. Keep only relevant body lines, marking **each omitted span** with `# ...` (or the source language's comment syntax). Do not begin the meaningful Python excerpt at a bare `return` or expression without showing the function it belongs to. Do not invent `def` / `class` for module-level code. |
| Quoting another file type. | Keep enough real syntax to establish scope: the heading for Markdown, parent keys for YAML/JSON, the `SELECT` or CTE name for SQL, or the nearest meaningful declaration for other languages. Retain actual language tags and syntax highlighting context; avoid bare, unscoped identifier fragments. Use the language's comment syntax for source-location annotations (`#` for YAML/Python, `--` for SQL, `<!-- -->` for Markdown). For JSON, tag an annotated excerpt `jsonc` with a `// path` comment; do not present that excerpt as strict JSON. |
| Quoting Markdown for its **meaning** rather than its syntax. | Prefer a short blockquote or your own explanation and a source link. If Markdown syntax itself matters, use a `markdown` fence, include the relevant heading, and quote only the necessary lines. |
| Proposing or reporting a code edit. | Provide **two separately labeled excerpts**, **BEFORE** and **AFTER**, covering the same relevant lines with the same enclosing scope. Never show only AFTER, and never use one source fence with prose about what changed. For proposed edits, label AFTER as proposed rather than suggesting it already exists at the linked source. Both excerpts retain the source location and path comment where a verified destination exists. |
| Showing a change inside a larger AFTER excerpt. | Mark inserted lines with `# NEW` and replaced lines with `# CHANGED`, using the language's comment syntax, and put the **old line commented immediately above** its replacement. Keep untouched context lines unmarked. These are annotated review snippets, not executable patches; do not imply that comments should be inserted into production code. |

**Illustrative Python excerpt** (the link below is a format illustration, not a verified source):

`[the_function — file and lines](src/path/to/file.py#L1-L8)`

```python
# src/path/to/file.py
class TheClass:
    # ...
    def the_function(self, arg):
        # ...
        a = b + c
```

For runnable shell commands, show an executable `sh` or `bash` fence with real argument values where appropriate; the source-excerpt rules above do not require inventing a containing function or a file link for a new command.
