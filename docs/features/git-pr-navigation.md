# 🔀 GitHub and Bitbucket PR navigation

[← Features](README.md) · [Git review](git-review.md)

This workflow uses the same shortcuts on both macOS profiles. The Git remote
determines which host is used; no separate GitHub/Bitbucket hotkeys are needed.

## ⌨️ Shortcuts

| Context | Shortcut | Result |
| --- | --- | --- |
| VS Code, inside a Git worktree | `Ctrl+P`, `Ctrl+R` | Find its open PR and open it in Chrome |
| Chrome or an installed Chrome web app, on a GitHub/Bitbucket PR or branch page | `Ctrl+Option+Cmd+V` | Open/create the source branch's linked worktree in VS Code |

For a normal Chrome tab, Hammerspoon reads the front Chrome window through
AppleScript (Automation permission). For installed Chrome web apps such as
GitHub.app, Hammerspoon captures the app at keypress and reads its document URL
through macOS Accessibility. It never substitutes an unrelated Chrome tab when
the web-app URL is unavailable. Hammerspoon needs Accessibility permission for
that app.

The VS Code global task **Git: Open Current Pull Request in Chrome** calls
`~/.local/bin/git-pr open-pr --path ${workspaceFolder}`. The companion task
**Git: Open Current Branch in Chrome** calls `git-pr open-remote`. The
Hammerspoon binding calls `git-pr open-local <browser-url>`.

## 🔄 Exact upsert behavior

**VS Code → PR:**

1. Determine the active branch and its Git remote (`github.com` or `bitbucket.org`).
2. For GitHub, open an existing source-branch PR, without pushing anything.
3. If no GitHub PR exists, only when the machine authorizes writes to this
   account, push a missing branch with upstream tracking and run
   `gh pr create --fill`. If the branch already exists remotely, do not push
   it again.
4. For Bitbucket, reuse the existing Chrome-backed PR lookup. If there is no
   PR, push a missing branch only on a professional-profile Mac; normal Git
   remote permissions apply. Open the branch page without creating a Bitbucket PR.

**Browser → VS Code:**

1. Resolve the PR's **source repository** and branch, including fork-based PRs.
   Preserve the PR's **destination repository** in the local branch configuration
   (`branch.<name>.prDestination`) so VS Code → PR searches the destination
   rather than the source fork. For manually configured forks, an `upstream`
   Git remote may supply the destination.
2. Locate the matching primary checkout under `REPOS_DIR` (or the Chezmoi
   `reposRoot` setting). Search immediate root and one child directory.
3. Clone a missing repository into `<reposRoot>/<repo>` without modifying
   other repositories. Refuse existing conflicting directory names.
4. Reuse a registered worktree on the branch. Otherwise fetch it and create
   `<primary-checkout>.worktrees/<branch-slug>`.
5. Open that directory in a new VS Code window. Never switch the primary
   checkout away from its default branch.

The command is idempotent: repeated requests reuse the same registered
worktree. GitHub branch-tree URLs with a file-path suffix resolve the longest
matching remote branch. A missing/deleted PR source repository fails rather
than guessing a substitute.

## 🔐 Write permissions by machine profile

Chezmoi renders `~/.config/pr-navigation/config.json` from
[`config.json.tmpl`](../../home/dot_config/pr-navigation/config.json.tmpl).

| Operation | `personal` profile | `professional` profile |
| --- | --- | --- |
| GitHub read/open/clone | Allowed | Allowed |
| GitHub branch push + PR creation | Only repositories whose owner is the configured `githubUsername` | **Never allowed** |
| Bitbucket read/open/clone | No company-repository checkout | Allowed |
| Bitbucket branch push | Disabled | Allowed without a workspace allowlist; Git remote permissions still apply |
| Bitbucket PR creation | Not implemented | Not implemented |

Bitbucket branch pushes on professional Macs do not use a separate
workspace allowlist. Git authentication and repository permissions determine
whether a push is accepted. Personal-profile Macs remain unable to push
Bitbucket branches, preserving the personal/work-machine separation.
Bitbucket PR creation is not implemented.

## 🛠️ Install and verify

`chezmoi apply` deploys `git-pr`, the existing Bitbucket Chrome helper,
and the Hammerspoon module, and merges the two global VS Code tasks/binding
without overwriting unrelated entries or comments. It uses the existing
Hammerspoon reload lifecycle.

Check the installed config and task behavior:

```bash
cat ~/.config/pr-navigation/config.json
git-pr open-remote --path "$PWD" --print
git-pr open-pr --path "$PWD" --print
```

**Important:** `--print` suppresses opening Chrome/VS Code but does **not**
disable clone, push, worktree creation or PR creation. Do not use it as a
dry-run for upsert actions. Testing uses isolated Git repositories and
subprocess stubs instead.
