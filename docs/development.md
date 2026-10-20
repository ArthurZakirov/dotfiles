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

### Step 2 — Create a feature branch if you plan to share the change (no Git worktree)

Skip this step for local-only settings such as `~/.zshrc.local`.

**Exception to the usual Git-worktree workflow:** Work directly in the checkout returned by `chezmoi source-path`. Do **not** create a separate Git worktree for this repository. Chezmoi uses its configured source directory, so `chezmoi cat`, `chezmoi diff`, and `chezmoi apply` would otherwise read the original checkout rather than changes made in a separate worktree.

From a clean working tree:

```sh
git switch main
git pull --ff-only
git switch -c feat/describe-change
code .
```

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
chezmoi add ~/.example
# Alternatively: chezmoi add --template ~/.example
```

**Option A — Edit chezmoi's source directly.** Open the appropriate tracked file:

| Purpose | File |
|---|---|
| Zsh configuration | [`home/dot_zshrc.tmpl`](../home/dot_zshrc.tmpl) |
| Personal-only configuration | [`home/.chezmoitemplates/personal.zsh`](../home/.chezmoitemplates/personal.zsh) |
| Chezmoi configuration | [`home/.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) |
| Shared template data | [`home/.chezmoidata.toml`](../home/.chezmoidata.toml) |
| Installers and packages | [`src/shell-setup.sh`](../src/shell-setup.sh), [`src/homebrew.sh`](../src/homebrew.sh), [`Brewfile`](../Brewfile) |

Inspect the generated output without applying it:

```sh
chezmoi cat ~/.zshrc
```

**Option B — Edit an existing, non-templated file already managed by chezmoi.** Replace `~/.example` with the actual managed path. Modify it directly, review the difference, then import the change into chezmoi's source:

```sh
code ~/.example
chezmoi diff ~/.example
chezmoi re-add ~/.example
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
4. After opening the PR in Step 5, check the [GitHub Actions workflow](../.github/workflows/shell.yml). Confirm both profile jobs and fresh-home jobs pass. Do **not** run the fresh-home provisioning tests on an existing Mac.

For testing architecture and CI coverage, see [Architecture](architecture.md#testing-and-validation).

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

### Step 6 — Update your local checkout after merging

```sh
git switch main
git pull --ff-only
```

### Step 7 — Preview and apply on this Mac

Follow [Already configured Mac: synchronize safely](setup.md#already-configured-mac-synchronize-safely).
