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
- Select tests by **observable user outcome**, not by the implementation boundary.
  Explicitly identify the user's real interaction (command, editor, GUI, login,
  OS service) and walk outward from mocked unit tests to real CLI integration,
  real provisioning/system tests, and, where the feature is user-facing, real
  application/GUI E2E using the actual application and APIs to verify its
  resulting state. Test the highest feasible safe layer and relevant lower
  layers; never label a mocked CLI call a verified user experience.
- Before calling work complete, ask: *What could still fail when the user
  performs this on their actual Mac, despite all present tests passing?*
  Turn credible gaps into observable regression tests. If an authentic layer
  cannot be run safely or in CI, document the unverified behavior and reason,
  instead of claiming end-to-end correctness. Prefer ephemeral CI environments
  for real GUI, launchd, or system integration; never experiment on the user's
  active desktop or remote access service.
- Inspect installed executable paths, service readiness, file ownership,
  configuration rendering, and safety *before* restarting an existing service.
- Follow the PR feedback loop: inspect all review threads; validate findings;
  implement warranted fixes with regression tests; run checks; commit/push;
  resolve only threads whose fixes were actually delivered. Do not merge
  automatically.
