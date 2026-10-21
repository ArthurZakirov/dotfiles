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
disposable worktree, including its `.venv`. Run `git unreview` from the review
folder, or from the source folder when exactly one review exists. Successful
cleanup unregisters and deletes the worktree, deletes its VS Code workspace,
and removes its now-empty cache directories without touching other reviews.

## Automatic Python setup in VS Code

For reviews containing **both `pyproject.toml` and `poetry.lock`**, the generated
`.code-workspace` includes an automatic VS Code folder-open task that invokes
the shared `~/.local/bin/pysetup` against the **review** checkout. It uses the
usual Poetry lock validation and dependency synchronization. Other repositories
open without this task. The editor opens first; setup executes in its terminal
without blocking `git review`.

Before VS Code opens, the helper calls
`pysetup --prepare-interpreter <review-folder>`. This phase creates a matching
checkout-local virtual environment with `uv venv` **without installing packages
or running project build hooks**. The interpreter therefore exists during VS
Code's initial environment discovery. The folder-open task subsequently
validates the Poetry lock and synchronizes dependencies under VS Code's
workspace trust and task-permission rules. This safe bootstrap can delay the
initial editor launch.

The same temporary workspace sets `python.defaultInterpreterPath` to
`${workspaceFolder}/.venv/bin/python`, so a fresh VS Code Python workspace can
use the checkout-local interpreter once it exists. This is a default, not a
forced `Python: Select Interpreter` command: VS Code's Python extension can
retain a previously selected interpreter, and environment detection may need a
refresh if it initialized before setup completed. Neither setting modifies the
reviewed repository or the user's global VS Code configuration.

Automatic tasks require VS Code to allow folder-open tasks and to trust the
workspace. An explicit trust prompt or a local `task.allowAutomaticTasks`
restriction takes precedence. **Only open and trust review worktrees whose
Python dependency/build scripts you intend to execute.** Git review does not
run `pysetup` outside VS Code or bypass VS Code's task security decisions.

The normal `code` CLI cannot select the Source Control sidebar. A small
managed extension at `~/.vscode/extensions/agentdesk.git-review-ui-0.1.0`
calls VS Code's `workbench.view.scm` command when a disposable review workspace
sets `gitReview.showSourceControl`. It has no effect in regular workspaces.
VS Code may need to be restarted once after the extension is installed via
chezmoi. Neither GitLens nor macOS keyboard focus is manipulated.

## Automatic per-file diff tabs

The review workspace also enables `gitReview.openDiffTabs`. After the built-in
Git extension discovers the isolated review repository, the same lightweight
extension opens **one persistent `vscode.diff` tab for each changed file**, not
a multi-file diff editor. Each right-hand document remains the actual review
worktree file, supporting ordinary editing and code navigation. Tabs are sorted
by relative path and opened with `preview: false`, so Ctrl+Tab can traverse them.
The extension does not open diff tabs in normal workspaces.

New files are compared against a read-only empty virtual document, making every
added line a diff addition (typically displayed green by VS Code); deleted
files are compared against an empty right-hand document. Their absence from
Git HEAD or the worktree does not prevent a diff tab from opening. Visual
colors depend on the user's VS Code theme and diff-editor configuration. Binary
files may use a non-text viewer rather than line-based highlighting.

The [isolated VS Code GUI test](../../tests/integration/test_git_review_vscode_gui.py)
asserts that the real editor opens separate, non-preview diff tabs with correct
old/new document contents, including added and deleted files. It does not
pixel-test the actual rendered colors or verify language-server navigation.

## 🧰 Installation and managed files

Both profiles receive this feature during normal
[setup or synchronization](../setup.md). Git and Python 3 are declared in the
[Brewfile](../../dependencies/brew/required.Brewfile), and the shared shell adds `~/.local/bin` to `PATH`.

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
removed by `git unreview`. The helper also clears repository-local Git environment
variables inherited from Git shell aliases (such as `GIT_DIR` and
`GIT_WORK_TREE`) before launching VS Code or running Git subprocesses.
Otherwise VS Code may report multiple apparent repositories with the same
source branch.

## Testing

[End-to-end tests](../../tests/integration/test_git_review_e2e.py) execute the
real Git aliases in isolated temporary repositories, including a regression for
checkout filters that previously caused `git apply --index` to fail. They check
review contents, isolation from the source checkout, and cleanup. Only the
VS Code launcher is stubbed so tests cannot replace an open editor window.
The [CI workflow](../../.github/workflows/shell.yml) runs these tests on both
macOS and Linux. It additionally installs actual VS Code on Ubuntu under Xvfb,
then executes the [real-editor GUI integration test](../../tests/integration/test_git_review_vscode_gui.py),
which verifies that the Git extension discovers exactly one review worktree
when the launcher inherits adversarial Git environment variables. The GUI test
uses a disposable VS Code profile and extensions directory, never the regular
VS Code user data. On macOS with the `code` CLI installed, run the same test via
`RUN_VSCODE_GUI_E2E=1 .venv/bin/pytest -q tests/integration/test_git_review_vscode_gui.py`.
