# 🔄 Automatically refresh permanent repositories

[← Feature index](README.md) · [Setup](../setup.md)

`repo-refresh` keeps repositories under one configured folder on their remote's
default branch. Before forcing a checkout or replacing local commits, it copies
the old working state into a recovery worktree. Feature branches remain checked
out in those recovery worktrees. Detached and default-branch work are preserved
as detached recovery worktrees with protected Git refs.
Existing linked development worktrees are excluded from permanent-clone discovery,
even when they currently live under the configured root.

## ⚙️ Install and configure

Install through the normal [dotfiles setup](../setup.md). The
[initial configuration](../../home/dot_config/repo-refresh/create_private_config.json.tmpl)
is created only when absent: subsequent applies preserve your local settings.
The personal profile enables the personal repository folder; the professional
profile starts disabled. Review the configuration before applying on an existing Mac.

Inspect or change the installed configuration:

```sh
cat ~/.config/repo-refresh/config.json
code ~/.config/repo-refresh/config.json
```

Set `root` to the folder whose repositories should be managed, and `worktrees`
to a separate recovery folder outside that root. Both accept `~`. Recovery paths
retain the repository's relative directory hierarchy, followed by a unique run
identifier. `remote` selects the remote, defaulting to `origin`; its advertised
default branch is resolved on every run, rather than assuming `main` or `master`.
Set `enabled` to `false` to pause future runs. An active run finishes normally.

The [LaunchAgent](../../home/private_Library/private_LaunchAgents/com.arthur.repo-refresh.plist.tmpl)
runs once at login/load and polls every minute while the Mac is awake. Slow runs
do not overlap. Offline/authentication failures are reported and retried on the
next scheduled run; credentials are never requested interactively. The
[installation hook](../../home/run_after_25-ensure-repo-refresh.sh.tmpl) loads the
service without restarting an active preservation transaction.

## 🛟 Preservation and recovery

Before replacement, the [updater](../../home/dot_local/bin/executable_repo-refresh)
preserves tracked files, staged versus unstaged changes, untracked files,
ignored files, symlinks, executable modes, and conflicted indexes. Submodule
gitfiles are converted into independent recovery metadata. Previous HEAD and
default-branch commits receive protected refs. In-progress merge/rebase metadata
is saved inside the recovery worktree's Git metadata as evidence; the recovery
worktree is for inspecting and continuing the preserved edits, not automatically
resuming the interrupted operation.

Find the latest result and recovery paths:

```sh
repo-refresh --status
# Run the same operation immediately:
repo-refresh
# Inspect a recovery path reported by status:
git -C /path/to/recovery status
git -C /path/to/recovery rev-parse --git-path repo-refresh/recovery.json
```

Recovery worktrees are private and never automatically deleted. They can contain
ignored credentials and large build directories. Check disk use and retain the
work you need before explicitly removing recovery worktrees and their protected
`refs/repo-refresh/` refs. The status file records the latest run; list all older
recovery worktrees with `git worktree list` in the repository.

After preservation, the permanent checkout is reset to the fetched default-branch
commit even after divergence, a force-push, or an interrupted operation. If that
default branch is checked out in another worktree, that other worktree is detached
at its existing commit, preserving its files and index. Ignored files remain in
the permanent checkout where possible; their recovery copies remain available.

If a fetch or preservation fails, no destructive checkout steps follow. Git lock
files, filesystem errors, nested linked worktrees, unsupported special files, and
files observed changing during the copy cause a reported failure and retry.
Other repositories continue updating. A failure after preservation leaves the
recovery worktree available even if checkout restoration needs another run.

**Treat the configured root as automatically replaceable.** Work in development
worktrees outside that root. Editors and agents do not obey this updater's lock:
change detection during copying reduces races but cannot guarantee preservation
of a save made after the final check. No background process can force checkout
while also guaranteeing every concurrent writer's data without their cooperation.

## 🧪 Verification

Run the real local-Git scenarios and isolated chezmoi installation checks:

```sh
.venv/bin/pytest -q tests/integration/test_repo_refresh.py
```

Tests use disposable repositories and local remotes. The macOS scheduler check
runs only on ephemeral CI; it never starts the updater against the developer's
repositories.
