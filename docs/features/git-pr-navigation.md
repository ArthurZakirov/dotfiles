# 🔀 GitHub and Bitbucket PR navigation

[← Features](README.md) · [Git review](git-review.md)

This workflow uses the same shortcuts on both macOS profiles. The Git remote
determines which host is used; no separate GitHub/Bitbucket hotkeys are needed.

## ⌨️ Shortcuts

| Context | Shortcut | Result |
| --- | --- | --- |
| VS Code, inside a Git worktree | `Ctrl+P`, `Ctrl+R` | Find its open PR and open it in Chrome |
| Chrome or an installed Chrome web app, on a GitHub/Bitbucket PR or branch page | `Ctrl+Option+Cmd+V` | Open/create the source branch's linked worktree in VS Code |
| VS Code or Chrome on a GitHub/Bitbucket page | `Ctrl+Option+Cmd+S` | [Find and open matching Codex/ChatGPT sessions](find-gpt-session.md) in existing Warp/Chrome windows |

For a normal Chrome tab, Hammerspoon reads the front Chrome window through
AppleScript (Automation permission). For installed Chrome web apps such as
GitHub.app, Hammerspoon captures the app at keypress and reads its document URL
through macOS Accessibility. It never substitutes an unrelated Chrome tab when
the web-app URL is unavailable. Hammerspoon needs Accessibility permission for
that app.

### Bitbucket inline comment → VS Code line

On a Bitbucket Cloud pull request, open a comment's permalink
(`https://bitbucket.org/<workspace>/<repo>/pull-requests/<PR>#comment-<ID>`)
and press **`Ctrl+Option+Cmd+V`**. The existing shortcut retrieves the
comment's `inline.path` and `inline.to` through the authenticated Chrome
Bitbucket session and opens the source-branch worktree at that file and line.
A reply follows its parent comment to the original inline anchor. Nothing
must be copied into VS Code.

Comments on deleted/old-side-only lines open the existing file **without a
line number**; no misleading old-side line is used. Non-inline PR comments
have no file to open and produce an explanatory error. If the file has been
deleted or moved from the checked-out branch, navigation reports that it is
missing instead of guessing another path. Current line numbers may drift if
the branch changed after the comment was made. File paths are validated
against the selected worktree; traversal and symlinks outside it are refused.
This feature currently targets **Bitbucket Cloud**, not GitHub comments.

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

## 🔑 Bitbucket Cloud SSH hostname migration

Atlassian is moving Git-over-SSH from `bitbucket.org` to **`ssh.bitbucket.org`**.
Controlled brownouts of the old SSH endpoint begin on November 12, 2026;
the final retirement is scheduled for December 10, 2026. Browser and API
URLs remain under `https://bitbucket.org/`.

The Git PR navigator and standalone Bitbucket helper treat all these Git
remotes as the **same repository**:

- Legacy: `git@bitbucket.org:workspace/repo.git`
- New: `git@ssh.bitbucket.org:workspace/repo.git`
- New SSH URI: `ssh://git@ssh.bitbucket.org/workspace/repo.git`
- Port 443 alternative: `ssh://git@altssh.bitbucket.org:443/workspace/repo.git`
- HTTPS: `https://bitbucket.org/workspace/repo.git`

New Bitbucket clones and saved PR destination remote URLs use the new SSH
hostname. **Existing Git remotes are not rewritten automatically.**
On the work Mac, inspect `git remote -v` and update an affected SSH remote
explicitly if it still uses the deprecated host:

```bash
git remote set-url origin git@ssh.bitbucket.org:<workspace>/<repo>.git
```

Keep the actual workspace, repository name and remote name from your existing
configuration. HTTPS remotes need no change. See the
[Atlassian SSH migration announcement](https://community.atlassian.com/forums/discussion/3234032/upcoming-change-to-bitbucket-cloud-ssh-access-move-from-bitbucket-org-to-ssh-bitbucket-org).

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
and the Hammerspoon module, and merges the three managed global VS Code tasks/binding
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
