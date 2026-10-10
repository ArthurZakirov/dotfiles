# Develop the repository

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

1. Add or adjust [unit tests](../tests/unit/test_shell_setup_module.sh) for installer logic and [integration tests](../tests/integration/test_profiles.py) for rendered behavior.
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

Wait for the pull request's required checks to pass, then merge it.

### Step 6 — Update your local checkout after merging

```sh
git switch main
git pull --ff-only
```

### Step 7 — Preview and apply on this Mac

Follow [Already configured Mac: synchronize safely](setup.md#already-configured-mac-synchronize-safely).
