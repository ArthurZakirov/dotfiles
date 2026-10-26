# 🔎 Code evidence and VS Code navigation

Use this procedure when responding to a question about real repository code and local editor access is available. This is backend execution guidance, independent of the realtime voice frontend.

## Establish the evidence location

1. Verify the relevant repository or Git worktree, its current revision, and the exact file and valid line number supporting the answer. Do not guess a similarly named checkout or location.
2. When local VS Code is available and the user has not requested otherwise, proactively open the **first relevant location** on the user's computer. For the first target in a repository, run `code --new-window "$repo" --goto "$file:$line"` using verified absolute paths. For a subsequent location in the same verified VS Code window, use `code --goto "$file:$line"`. If the active editor workspace is uncertain or the repository changes, use a new window.
3. Check the editor command's exit status; when a suitable UI inspection tool is available, verify that VS Code actually displays the intended file and line. A successful CLI exit by itself does not establish visible navigation. If local editor control is unavailable, give the user one exact, manually accessible path and line instead.
4. Ground each code claim in the actual inspected source. For an ordinary code question, provide the requested answer and verified location rather than requiring a staged walkthrough unless the user wants to follow it interactively.

## Guided interactive walkthroughs

When the user requests to follow evidence visually, or a voice frontend delegates an interactive code walkthrough:

1. Open only the first verified evidence location and return a single location-only checkpoint. Ask the user to confirm the target is visible; do not spoil its meaning or preview the conclusion.
2. After confirmation, if the next step is merely a direct navigation waypoint toward a declaration, provide only the next immediate navigation action. For a distinct evidence location, first explain what the currently visible code contributes and how it connects to the preceding evidence. Do not navigate to another evidence file in the same reply.
3. Treat each editor movement and explanation as a separate checkpoint. Wait for the user's confirmation, interruption, or request before moving forward. If the user becomes lost, re-establish the current location.
4. Verify each new target independently. Do not assume that the user's editor follows a CLI command successfully, or that another file establishes a fact before it is inspected.

For multihop relationships (for example, input configuration → parser → authorization → query), keep the user on one verified location at a time and explain that location before continuing.
