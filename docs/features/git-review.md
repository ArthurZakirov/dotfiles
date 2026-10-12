# 🔎 Git review

[← Features](README.md) · [How it works](../architecture.md)

Open a commit or branch diff as editable changes in a disposable folder. The
source branch, commits, and uncommitted edits remain untouched.

| Command | Review |
| --- | --- |
| `git review <commit>` | One commit against its parent |
| `git review-range` | HEAD against the fetched upstream remote's default branch |
| `git review-range <base> [<target>]` | An explicit range using its merge base |
| `git unreview` | Return to the source folder and remove the disposable review |

The `code` CLI opens the review in VS Code when available; otherwise the command
prints the review folder. VS Code displays a named workspace such as
`provisioning · review · d5a4611` (including the repository and target commit),
while the reviewed files stay inside the disposable Git worktree.
Reviews use detached worktrees under
`~/.local/share/git-review/`. Closing a review discards edits made inside that
disposable worktree. Run `git unreview` from the review folder, or from the source
folder when exactly one review exists.

## 🧰 Installation and managed files

Both profiles receive this feature during normal
[setup or synchronization](../setup.md). Git and Python 3 are declared in the
[Brewfile](../../Brewfile), and the shared shell adds `~/.local/bin` to `PATH`.

Chezmoi manages the [global configuration](../../home/dot_gitconfig) at
`~/.gitconfig` and the
[helper](../../home/dot_local/bin/executable_git-review-worktree) at
`~/.local/bin/git-review-worktree`. On its first apply, the
[migration script](../../home/run_once_before_15-migrate-git-config.sh) preserves
an existing `~/.gitconfig` as `~/.gitconfig.local`.

`~/.gitconfig.local` is unmanaged, created empty when needed, and takes
precedence over the shared configuration. Put this machine's `user.name`,
`user.email`, signing key, credential helper, and employer-specific settings
there. This lets personal and professional Macs use different Git identities
without copying either into the shared repository.

Review metadata is stored as `GIT_REVIEW.json` in the disposable worktree's Git
metadata directory, so it does not appear among the reviewed changes. The
VS Code workspace file is instead stored outside both the review worktree
and the source repository (`~/.local/share/git-review/.../workspaces/`).
Keeping the workspace file outside `.git/worktrees/` prevents VS Code from
wrongly discovering the source checkout as extra Git repositories. It is
removed by `git unreview`.

## Testing

[End-to-end tests](../../tests/integration/test_git_review_e2e.py) execute the
real Git aliases in isolated temporary repositories, including a regression for
checkout filters that previously caused `git apply --index` to fail. They check
review contents, isolation from the source checkout, and cleanup. Only the
VS Code launcher is stubbed so tests cannot replace an open editor window.
The [CI workflow](../../.github/workflows/shell.yml) runs these tests on both
macOS and Linux.
