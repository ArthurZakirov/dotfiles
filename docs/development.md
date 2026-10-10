# Develop the repository

[← README](../README.md) · [Architecture](architecture.md)

## Change and share configuration

Chezmoi edits the managed source and can show the rendered difference:

```sh
chezmoi edit ~/.zshrc
chezmoi diff
chezmoi apply
chezmoi git -- add .
chezmoi git -- commit -m "Update shared shell configuration"
chezmoi git -- push
```

The [chezmoi config template](../home/.chezmoi.toml.tmpl) configures VS Code for editing and diff views. Another Mac can fetch and apply committed changes with `chezmoi update`.

Reusable implementation belongs in [`src/`](../src/shell-setup.sh); lifecycle entry points belong in the [chezmoi hooks](../home/run_before_10-install-shell.sh.tmpl). Keep functions reusable rather than copying installer logic. `install_editors` orchestrates concrete editor installers (currently `install_visual_studio_code`). `install_profile` dispatches to `install_personal_profile` or `install_professional_profile`; each profile function invokes concrete tool installers (for example, `install_bitwarden_secrets_manager`). To add another editor or profile-specific tool, add its installer and call it from the corresponding orchestrator. Update the [Brewfile](../Brewfile) for required Homebrew packages, [chezmoi data](../home/.chezmoidata.toml) for shared settings, and the [zsh template](../home/dot_zshrc.tmpl) for shell behavior. Personal-only additions belong in [personal.zsh](../home/.chezmoitemplates/personal.zsh); local-only overrides can be placed in untracked `~/.zshrc.local`.

## Tests

The local test runner is **read-only with respect to your Mac's setup**: it renders templates, validates syntax, and stubs installation functions rather than running the installers. Python behavior tests use **pytest** in a Poetry-managed, project-local `.venv`; parameterized fixtures exercise both machine profiles. Install Poetry separately as a development tool (it is intentionally not part of machine provisioning). Then run:

```sh
poetry config virtualenvs.in-project true --local
poetry sync
./tests/run.sh
```

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
