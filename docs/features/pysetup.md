# Python virtual environments (pysetup)

[← Features](README.md)

`pysetup [checkout-directory]` creates or reuses a checkout-local `.venv` from an **existing, fresh Poetry lockfile**. It requires `pyproject.toml`, `poetry.lock`, and `uv` (installed via the required [Brewfile](../../dependencies/brew/required.Brewfile)). It does **not** resolve or update the project's dependency versions.

- Verifies a cache-miss lock with pinned Poetry 2.4.1 and poetry-plugin-export 1.10.1, then exports all groups with hashes.
- Uses a content-addressed export cache in `~/Library/Caches/pysetup` and `uv pip sync --require-hashes`.
- Reuses an existing compatible environment, never silently replaces an incompatible one.
- Installs the project in editable mode unless Poetry's `package-mode = false`.
- Avoids tracked project changes; if needed, adds `.venv/` to local Git `info/exclude`.
- Hides subprocess diagnostics that could expose private package credentials. Embedded URL credentials/query strings are rejected before installation.

Example: `cd path/to/project && pysetup` or `pysetup path/to/project`.

The first run may download an interpreter and packages. Do not run against a checkout with untrusted dependency specifications. The target must be a Poetry-managed project; standalone uv-only projects are outside scope.

Implementation: [executable_pysetup](../../home/dot_local/bin/executable_pysetup). Tests: [unit](../../tests/unit/test_pysetup.py) and [integration](../../tests/integration/test_pysetup.py).
