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

### Step 3 — Edit the source

Change the repository templates rather than generated files under `$HOME`:

| Purpose | File |
|---|---|
| Zsh configuration | [`home/dot_zshrc.tmpl`](../home/dot_zshrc.tmpl) |
| Personal-only configuration | [`home/.chezmoitemplates/personal.zsh`](../home/.chezmoitemplates/personal.zsh) |
| Chezmoi configuration | [`home/.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) |
| Shared template data | [`home/.chezmoidata.toml`](../home/.chezmoidata.toml) |
| Installers and packages | [`src/shell-setup.sh`](../src/shell-setup.sh), [`src/homebrew.sh`](../src/homebrew.sh), [`Brewfile`](../Brewfile) |

Edit the relevant file, then inspect the rendered result before writing tests:

```sh
chezmoi cat ~/.zshrc
```

For repository structure and installer responsibilities, see [Architecture](architecture.md).

### Step 4 — Write tests and run them

Install Poetry separately as a development tool, then set up project-local dependencies:

```sh
poetry config virtualenvs.in-project true --local  # Once per checkout
poetry sync
./tests/run.sh
```

If an intentional template change modifies the rendered `.zshrc` or chezmoi TOML, update the reviewed fixtures and inspect the diff:

```sh
poetry run python -m tests.support.update_rendered_snapshots
git diff -- tests/fixtures/rendered/
./tests/run.sh
```

Do not regenerate snapshots merely to silence a failing test. Running tests does not apply configuration to your Mac.

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

```sh
chezmoi diff
chezmoi apply
```

If [`.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) changed, first back up the existing chezmoi configuration and run `chezmoi init` (without `--apply`). Review `chezmoi diff` and run `chezmoi apply` **only if you accept the changes**. See [Setup](setup.md#already-configured-mac-synchronize-safely) for another Mac.

## Test checklist

1. Add or adjust [unit tests](../tests/unit/test_shell_setup_module.sh) for installer logic and [integration tests](../tests/integration/test_profiles.py) for rendered behavior.
2. Run `./tests/run.sh` and fix any failures.
3. If rendered configuration changed intentionally, regenerate the [snapshots](../tests/fixtures/rendered/) using the command in [Step 4](#step-4--write-tests-and-run-them); review the diff before committing.
4. Check the [GitHub Actions workflow](../.github/workflows/shell.yml) after opening the PR. Confirm both profile jobs and fresh-home jobs pass. The fresh-home jobs provision only ephemeral macOS CI environments; do **not** run them on an existing Mac.

For how the testing components work and what CI does not cover, see [Architecture](architecture.md#testing-and-validation).
