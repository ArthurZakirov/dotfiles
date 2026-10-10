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

### Step 2 — Create a feature branch

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
| Zsh configuration | [`dot_zshrc.tmpl`](../home/dot_zshrc.tmpl) |
| Personal-only configuration | [`personal.zsh`](../home/.chezmoitemplates/personal.zsh) |
| Chezmoi configuration | [`.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) |
| Shared template data | [`.chezmoidata.toml`](../home/.chezmoidata.toml) |
| Installers and packages | [`shell-setup.sh`](../src/shell-setup.sh), [`homebrew.sh`](../src/homebrew.sh), [`Brewfile`](../Brewfile) |

Reusable installer functions belong in `src/`; [lifecycle hooks](../home/run_before_10-install-shell.sh.tmpl) orchestrate them. Keep machine-local overrides in untracked `~/.zshrc.local`.

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

Review the diff, CodeRabbit feedback, and GitHub Actions results. Fix issues on the branch and merge the PR only when the checks pass.

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

Inspect the diff **before** applying. `chezmoi apply` runs applicable lifecycle hooks, including the idempotent package installer. If [`.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) changed, review/back up your existing chezmoi configuration and run `chezmoi init` to regenerate it **without** `--apply` before previewing. On another Mac, fetch changes explicitly with `chezmoi update` after reviewing what will be applied; it fetches and applies in one operation.

## Tests

The local test runner is **read-only with respect to your Mac's setup**: it renders templates, validates syntax, and stubs installation functions rather than running installers. Python behavior tests use **pytest** in a Poetry-managed, project-local `.venv`; parameterized fixtures exercise both machine profiles. See [Step 4](#step-4--write-tests-and-run-them) for setup and execution commands.

`pyproject.toml` and `poetry.lock` define the reproducible test dependencies. `.venv/` and `poetry.toml` are local-only and should not be committed.

### Finding and extending tests

Tests are organized by behavior: `tests/unit/` isolates installer orchestration with stubbed dependencies, while `tests/integration/` exercises real chezmoi rendering, zsh startup, and CI-only fresh-home provisioning. Reusable fixtures and assertions live in `tests/support/`.

Each test describes **Given / When / Then** and has a descriptive name, so a reader can skim the behavior without following subprocess arguments or setup logic.

- [Shell orchestration tests](../tests/unit/test_shell_setup_module.sh) verify editor and profile factory dispatch. Their [fixture](../tests/support/shell_setup_fixture.sh) replaces concrete installers with in-memory spies.
- [Profile rendering tests](../tests/integration/test_profiles.py) verify generated config, both zsh profiles, hook syntax, and interactive startup. Their [chezmoi fixture](../tests/support/chezmoi_profile.py) handles temporary files and subprocesses.
- [Fresh-home integration test](../tests/integration/run_fresh_home.sh) describes a clean-machine scenario; its [fixture](../tests/support/fresh_home_fixture.sh) isolates the macOS home directory and performs real provisioning. Shared shell assertions live in [`tests/support/assertions.sh`](../tests/support/assertions.sh).

Rendered `.zshrc` and chezmoi TOML configurations for both profiles are locked down in [`tests/fixtures/rendered/`](../tests/fixtures/rendered/). The integration tests render these configurations, normalize machine-specific absolute paths to `<HOME>` and `<DOTFILES_REPO>`, and compare the results byte-for-byte with committed snapshots. Lifecycle scripts are syntax-checked separately, without full-output snapshots. If a template change intentionally affects generated files, regenerate the fixtures with `python3 -m tests.support.update_rendered_snapshots`, review the Git diff, and commit the resulting snapshot changes alongside the template. Never blindly regenerate them to make a failing test pass.

The [test runner](../tests/run.sh) orchestrates syntax, behavior, and whitespace checks.

### How the clean-machine path is tested

[macOS GitHub Actions](../.github/workflows/shell.yml) provisions **separate temporary HOME directories for both personal and professional profiles** on ephemeral macOS runners via `chezmoi init --apply`, exercising real installation hooks, profile-specific integrations, and GitHub username discovery for branch pushes. It does not provision the developer's existing Macs. The runner already includes macOS tooling, including Homebrew, so CI does **not** prove the Homebrew-from-zero or macOS permission prompts on a completely blank physical Mac. A Linux devcontainer cannot faithfully cover those macOS-specific steps.

Review your Git diff and CI checks before publishing changes. Do not run a destructive first-time provisioning test on an existing Mac.
