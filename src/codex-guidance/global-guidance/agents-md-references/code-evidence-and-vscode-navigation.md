# 🔎 Code evidence and VS Code navigation

Use this procedure when responding to a question about repository code.

## Establish the evidence location

1. Verify the relevant repository or Git worktree, its current revision, and the exact file and valid line number supporting the answer. Do not guess a similarly named checkout or location.
2. When local VS Code is available and the user has not requested otherwise, proactively open the **first relevant location** on the user's computer. For the first target in a repository, run `code --new-window "$repo" --goto "$file:$line"` using verified absolute paths. For a subsequent location in the same verified VS Code window, use `code --goto "$file:$line"`. If the active editor workspace is uncertain or the repository changes, use a new window.
3. Check the editor command's exit status; when a suitable UI inspection tool is available, verify that VS Code actually displays the intended file and line. A successful CLI exit by itself does not establish visible navigation. If local editor control is unavailable, give the user one exact, manually accessible path and line instead.
4. Ground every code claim in the inspected source and make its verified location directly accessible to the user.
