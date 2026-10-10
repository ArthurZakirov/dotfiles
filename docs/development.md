# Develop the repository

[← README](../README.md) · [Architecture](architecture.md)

## Development workflow

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

### Step 2 — Create a feature branch (no Git worktree)

**Exception to the usual Git-worktree workflow:** Work directly in the checkout returned by `chezmoi source-path`. Do **not** create a separate Git worktree for this repository. Chezmoi uses its configured source directory, so `chezmoi cat`, `chezmoi diff`, and `chezmoi apply` would otherwise read the original checkout rather than changes made in a separate worktree.

From a clean working tree:

```sh
git switch main
git pull --ff-only
git switch -c feat/describe-change
code .
```

### Step 3 — Edit or add dotfiles

**New file only:** Create the file in `$HOME`, then start tracking it with chezmoi before editing its source:

```sh
chezmoi add ~/.example
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

### Professional Mac — Keep work-only shell settings local

1. On the professional Mac, create or edit the unmanaged override file:

   ```sh
   touch "$HOME/.zshrc.local"
   code "$HOME/.zshrc.local"
   ```

2. Add work-specific aliases, environment variables, or paths, for example:

   ```zsh
   export WORK_PROJECTS="$HOME/Repos/professional"
   alias work='cd "$WORK_PROJECTS"'
   ```

3. Reload the shell to pick up the changes:

   ```sh
   exec zsh
   ```

4. To receive published shared changes, follow [Already configured Mac: synchronize safely](setup.md#already-configured-mac-synchronize-safely), or run `chezmoi update` **only when the chezmoi source checkout is clean and tracking the intended upstream branch**.

Do **not** run `chezmoi add` or `chezmoi re-add` on `~/.zshrc.local`, and do not commit it. The managed [`home/dot_zshrc.tmpl`](../home/dot_zshrc.tmpl) already sources that file when readable; `chezmoi update` does not manage it.
