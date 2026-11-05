# Develop DevMac

[← README](../README.md) · [Architecture](architecture.md)

## Development workflow

### Step 0 — Decide the sharing scope

| Sharing scope | Action |
|---|---|
| **Local only** (not version-controlled; e.g., work-specific settings) | Keep the file outside chezmoi. For shell settings use `~/.zshrc.local`; skip Steps 1–2 and go directly to Step 3. Do not commit it. |
| **Version-controlled, shared across profiles** | Edit or add a managed file without profile conditions. Follow Steps 1–7. |
| **Version-controlled, profile-specific** | Edit or add a managed template using a condition for `personal` or `professional`. Follow Steps 1–7. This is **committed to the shared Git repository**; do not store work secrets or confidential data there. |

### Step 1 — Open the repository

```sh
chezmoi cd
```

Chezmoi opens a shell in its source directory (`home/` in this repository). **In that shell**, switch to the Git root and inspect the working tree:

```sh
cd "$(git rev-parse --show-toplevel)"
git status --short --branch
```

Check existing changes before switching branches.

### Step 2 — Create a feature worktree if you plan to share the change

Skip this step for local-only settings such as `~/.zshrc.local`.

**Do not check out feature branches in the permanent Chezmoi source checkout.** Create a sibling worktree for each feature branch. Chezmoi's default source still points to the permanent checkout, so use `chezmoi --source "$PWD/home"` from a feature worktree only when deliberately previewing its templates; after merging, update the permanent checkout and run a normal `chezmoi apply`.

From the permanent checkout, first fetch the latest default branch:

```sh
git fetch origin main
git worktree add -b feat/describe-change ../dotfiles.worktrees/feat-describe-change origin/main
cd ../dotfiles.worktrees/feat-describe-change
code .
```

Do not move or discard uncommitted work to establish this layout. If a branch is already checked out in the permanent checkout, preserve its tracked, untracked, and ignored files before relocating it; use the repository refresh service or another explicitly verified migration procedure.

#### Run Chezmoi from a feature worktree

Chezmoi defaults to the source directory in `~/.config/chezmoi/chezmoi.toml`, **not** the directory where the shell is running. From the feature worktree's repository root, override the source for each command using the global `--source` / `-S` flag:

```sh
# Run these commands from the feature worktree's root (not its home/ directory).
source_dir="$PWD/home"
chezmoi --source "$source_dir" source-path
chezmoi --source "$source_dir" cat ~/.config/repo-refresh/config.json
chezmoi --source "$source_dir" status
chezmoi --source "$source_dir" --use-builtin-diff diff
chezmoi --source "$source_dir" apply --dry-run --verbose
# Only when you explicitly want to change THIS Mac:
chezmoi --source "$source_dir" apply
```

`--source` selects the worktree's `home/` directory for template rendering and file installation **without changing** your globally configured Chezmoi source. The default `chezmoi diff` invokes a custom VS Code diff adapter configured to target the permanent repository window. Use `--use-builtin-diff` for an accurate terminal diff, or set `CHEZMOI_CODE_DIFF_WORKSPACE="$PWD"` before `chezmoi --source "$PWD/home" diff` to direct the VS Code diff tabs to this worktree.

**Applying is a live operation:** `apply` changes files in your real home directory and may run lifecycle scripts or restart services; `--source` does *not* sandbox those side effects. Prefer the dry run and integration tests while developing. After merging, update the permanent checkout and apply the merged version from there. Never run `chezmoi update` in a feature worktree as a shortcut for syncing the permanent checkout.

### Step 3 — Edit or add dotfiles

Before changing anything, **inspect the actual Mac read-only**. Identify existing managed files, installed executables and their paths, active services/LaunchAgents, current profile, and local modifications relevant to the feature. Compare this state with the proposed change: what could be overwritten, restarted, disconnected, or removed? Preserve existing user state; never probe by restarting a live service or applying changes. If the target Mac is inaccessible, state which risks remain unverified and test them in isolation before proceeding.

Use the sharing scope selected in [Step 0](#step-0--decide-the-sharing-scope).

**Local-only shell overrides** (on whichever Mac needs them):

```sh
touch "$HOME/.zshrc.local"
code "$HOME/.zshrc.local"
# After saving your changes:
exec zsh
```

The managed [`home/dot_zshrc.tmpl`](../home/dot_zshrc.tmpl) already sources `~/.zshrc.local`. Leave this local file unmanaged so subsequent shared updates do not overwrite it. For other local-only configuration files, use the application's supported local include or override mechanism. **For local-only changes, stop here; Steps 4–7 concern version-controlled changes.**

**For version-controlled changes, use one of these workflows:**

**New file only:** Create it in `$HOME`, then register it with chezmoi (use `--template` if the new file needs profile conditions):

```sh
chezmoi --source "$PWD/home" add ~/.example
# Alternatively, for a template:
chezmoi --source "$PWD/home" add --template ~/.example
```

**Option A — Edit chezmoi's source directly.** Open the appropriate tracked file:

| Purpose | File |
|---|---|
| Zsh configuration | [`home/dot_zshrc.tmpl`](../home/dot_zshrc.tmpl) |
| Personal-only configuration | [`home/.chezmoitemplates/personal.zsh`](../home/.chezmoitemplates/personal.zsh) |
| Chezmoi configuration | [`home/.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) |
| Shared dependency revisions | [`dependencies/git/`](../dependencies/git/) |
| Installers and packages | [`src/shell-setup.sh`](../src/shell-setup.sh), [`src/apps.sh`](../src/apps.sh), [`dependencies/`](../dependencies/) |

Inspect the generated output without applying it:

```sh
chezmoi --source "$PWD/home" cat ~/.zshrc
```

**Option B — Edit an existing, non-templated file already managed by chezmoi.** Replace `~/.example` with the actual managed path. Modify it directly, review the difference, then import the change into chezmoi's source:

```sh
code ~/.example
chezmoi --source "$PWD/home" --use-builtin-diff diff ~/.example
chezmoi --source "$PWD/home" re-add ~/.example
```

`chezmoi re-add` does **not** overwrite templates. For a templated file such as `~/.zshrc`, use Option A and edit [`home/dot_zshrc.tmpl`](../home/dot_zshrc.tmpl) instead. Inspect the Git diff after either option.

For repository structure and installer responsibilities, see [Architecture](architecture.md).

### Step 4 — Write tests and run them

First define the **observable user outcome** (CLI result, editor state, or running service). Choose the highest safe test fidelity needed to verify it. A stubbed call does not prove real GUI or OS behavior; use ephemeral CI for actual VS Code or launchd tests, never the active Mac.

For every feature, consider fresh install, existing files, upgrade, repeated apply, partial failure, and recovery. Add feature-specific regression tests for risks the shared lifecycle test cannot verify, including executable paths and application state. Document any remaining unverified real-world behavior.

1. Add feature-specific [unit tests](../tests/unit/test_shell_setup_module.sh), [profile tests](../tests/integration/test_profiles.py), and higher-fidelity tests where needed. The [shared lifecycle test](../tests/integration/test_chezmoi_lifecycle.py) automatically exercises all managed files through real `chezmoi diff` and `apply` in an isolated HOME, with install hooks and the GUI stubbed. Verify those separately when relevant.
2. Install Poetry separately as a development tool. Set up the project-local environment and run the tests:

   ```sh
   poetry config virtualenvs.in-project true --local  # Once per checkout
   poetry sync
   ./tests/run.sh
   ```

3. Fix failing tests. If a change intentionally affects any snapshotted rendered file, regenerate the [snapshots](../tests/fixtures/rendered/), inspect their diff, and rerun the tests. When adding a new managed configuration file, add appropriate rendering tests and snapshots if useful:

   ```sh
   poetry run python -m tests.support.update_rendered_snapshots
   git diff -- tests/fixtures/rendered/
   ./tests/run.sh
   ```

   Do not regenerate snapshots merely to silence a failing test. These tests do not apply configuration to your Mac.
4. After opening the PR in Step 5, check the [GitHub Actions workflow](../.github/workflows/shell.yml). Confirm `ci-sanity` and all affected system jobs pass; unrelated jobs should be marked skipped. To verify every job, use the manual workflow trigger. Do **not** run the fresh-home provisioning tests on an existing Mac.

For testing architecture and CI coverage, see [Architecture](architecture.md#testing-and-validation).

### GitHub Actions: selective CI

The [shell workflow](../.github/workflows/shell.yml) starts a cheap Ubuntu
`ci-sanity` check on every PR and push to `main`. This validates shell syntax,
documentation contracts, and the selective-CI decision tests.

Expensive macOS and real GUI/E2E jobs are selected by
[`src/ci/select_jobs.py`](../src/ci/select_jobs.py) from the actual changed
files. The selector encodes direct dependencies (for example, a change to
`executable_pysetup` also triggers Git-review integration tests). Changes limited
to `README.md`, `docs/**`, or repository-local `.vscode/**` run only
`ci-sanity`. Unrecognized paths, shared dependencies, CI changes, and changes
to the selector itself **run all system jobs**, rather than risking a false
negative. A diff that cannot be established or is truncated also runs all
jobs.

To check the decision table locally:

```sh
python3 -m pytest -q tests/unit/test_ci_select_jobs.py
```

To run every CI job intentionally, start **Validate Mac shell profiles** using
GitHub Actions' **Run workflow** button (`workflow_dispatch`). PR supersessions
cancel previous PR runs; pushes to `main` are not cancelled. When introducing
a new production component or E2E dependency, extend the classifier and its
tests in the same PR. Do not add broad skip rules without evidence of
independence.

### Step 5 — Review and open a pull request

```sh
git diff --check
git status --short
git add <changed-files>
git commit -m "Describe the change"
git push -u origin HEAD
gh pr create --fill
```

After opening the PR, inspect both inline review threads and general comments.
For each actionable finding, verify it against the current code, add a
regression test, implement the fix, run the full checks, and push it to the
same branch. Mark a review thread resolved **only after** its fix is committed
and pushed; explain explicitly when a suggestion is not applicable.
Wait for required checks to pass. Merge only when the user requests it.

### Step 6 — Update the permanent checkout after merging

The feature worktree is not the permanent Chezmoi source. After merging the PR,
update the permanent checkout (or let the enabled repository refresh service
do this when it is safe). Never switch an active feature worktree to `main`.

```sh
git -C "$(dirname "$(chezmoi source-path)")" switch main
git -C "$(dirname "$(chezmoi source-path)")" pull --ff-only
```

If the permanent checkout currently contains another agent's branch or edits, do
not force the switch or pull. Wait for a verified repository refresh to preserve
and relocate that work first.

### Step 7 — Preview and apply on this Mac

Follow [Already configured Mac: synchronize safely](setup.md#already-configured-mac-synchronize-safely).
