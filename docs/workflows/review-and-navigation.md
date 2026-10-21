# Keep up with your agents

[← DevMac](../../README.md) · [Feature index](../features/README.md)

## Make a thorough review easy to start

An agent can write thousands of lines before you have opened the first diff. If reviewing those changes requires hunting down a branch, preparing a Python environment, navigating files, and looking up tickets or documentation across apps, it becomes tempting to skim the code, say “looks good to me,” and move on. The result can be a pull request—or production code—that you have barely inspected.

DevMac makes the actual changes, tests, and surrounding context easier to reach. That lowers the effort required to **do the review**, rather than simply approve it.

## Navigate to the evidence

| What you need to do | How DevMac helps | Detail |
| --- | --- | --- |
| Understand exactly what an agent changed | Open a disposable Git review worktree with individual, persistent VS Code diff tabs | [Git review](../features/git-review.md) |
| Explore or run a Python checkout under review | Prepare a checkout-local environment from the existing Poetry lockfile, integrated with review workspaces | [Python environments](../features/pysetup.md) |
| Launch applications quickly | Find and open installed apps with Raycast | [Raycast navigation](../features/raycast.md) |
| Jump to a repository or configuration file | Use the Raycast Repository Manager extension or managed Script Commands to open it in VS Code | [Raycast navigation](../features/raycast.md) |
| Recall and execute shell commands quickly | Search history and completions with the configured Zsh environment and fzf | [Zsh configuration](../features/zsh.md) |
| Switch applications, windows, or Spaces without hunting with the pointer | Use native shortcuts and Hammerspoon bindings; AltTab offers window switching | [macOS shortcuts](../features/macos-shortcuts.md) · [Hammerspoon](../features/hammerspoon.md) |
| Work in a terminal or inspect files visually | Use the provisioned Warp terminal, VS Code, and browser | [Tool inventory](../tool-inventory.md) |

Raycast is installed as an app launcher, and chezmoi provides file-opening Script Commands. The Script Commands directory and optional Repository Manager extension require one-time setup on each Mac; neither is necessary for other DevMac capabilities. Warp is installed as a terminal choice.

## Example: review before you accept

1. Start from the agent's commit or branch and run `git review <commit>` or `git review-range`.
2. Walk the individual diff tabs in VS Code, inspect context, and run relevant tests. For Poetry projects, the review workspace can prepare its own Python environment.
3. Use Raycast to find applications, repositories, and configuration files (after completing its optional navigation setup), or use the shell; use the browser for linked tickets or documentation.
4. Return to the agent with concrete review findings, not only a summary of what it says it did. Exit the isolated review with `git unreview`.

**The easier it is to reach the evidence, the more practical a complete review becomes.**

[Window, display, and multi-Mac navigation →](workspace-control.md)
