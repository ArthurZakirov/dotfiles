@README.md

## Feature development and lifecycle verification

Before changing managed state, inspect `docs/development.md` and the nearest
existing feature/tests. Treat every new managed file, template, or hook as a
change to the whole chezmoi lifecycle, not an isolated installer change.

- Preserve the real user's HOME, active LaunchAgents, and credentials. Run
  destructive provisioning only in an isolated test HOME or ephemeral CI Mac.
- Run the repository-wide chezmoi lifecycle tests for both profiles on every
  feature change; they must automatically include new managed files. Add
  feature-specific tests for dependencies, initial installation, repeated
  apply, local drift, upgrade from prior state, error recovery, and rollback
  as applicable. A mocked dependency call is not proof of real provisioning.
- Inspect installed executable paths, service readiness, file ownership,
  configuration rendering, and safety *before* restarting an existing service.
- Follow the PR feedback loop: inspect all review threads; validate findings;
  implement warranted fixes with regression tests; run checks; commit/push;
  resolve only threads whose fixes were actually delivered. Do not merge
  automatically.
