# 🔄 Keep repositories and feature branches current

[← Feature index](README.md) · [Dotfiles setup](../setup.md)

`repo-refresh` keeps permanent clones on the latest remote default branch and
rebases local feature branches onto it. It preserves recovery copies before
rewriting work and leaves conflicts visible for you to resolve. Unreadable
historical recovery worktrees are retained without preventing maintenance of
other branches in the same repository.

## ⚙️ Install and configure

Use the normal dotfiles installation flow:

1. **Choose the versioned feature state** in
   [`home/.chezmoidata.toml`](../../home/.chezmoidata.toml). Set
   `repoRefresh.enabled = true` to enable or `false` to disable. The default
   is **true**; you can explicitly disable the scheduled updater when needed.
   Existing conflicted worktrees remain preserved for later manual resolution;
   they do not have to be resolved before enabling the service. On fresh Macs,
   the installation hook creates the configured repository root if necessary
   before it starts the LaunchAgent.
2. **Run `chezmoi apply`** following the [setup guide](../setup.md).
   Chezmoi rewrites the [runtime configuration](../../home/dot_config/repo-refresh/private_config.json.tmpl)
   and regenerates the global `~/.codex/AGENTS.md` from the same value.
3. **Verify actual service state.** On macOS, the
   [installation hook](../../home/run_after_25-ensure-repo-refresh.sh.tmpl)
   enables and loads the LaunchAgent when the value is `true`, or disables
   and unloads it when `false`. Repeated applications reconcile an already
   loaded or previously disabled service. If a refresh holds the run lock,
   the hook does not interrupt it; reapply after the active transaction finishes.

The configuration fields define the managed scope:

| Field | What to set |
| --- | --- |
| `root` | Directory containing permanent clones directly (no nested repository groups). |
| `remote` | Remote whose advertised default branch should be followed. |
| `enabled` | Rendered from the versioned `repoRefresh.enabled` feature switch; controls both the updater and the macOS LaunchAgent. |

The root is set during chezmoi initialization via `REPOS_DIR` (saved as
`reposDir` in the local chezmoi configuration; default:
`~/Repos`), used by the shell and the initial repo-refresh configuration.
The rendered `~/.config/repo-refresh/config.json` is not an independent
configuration source: later `chezmoi apply` runs replace manual edits.
Change the versioned switch in `home/.chezmoidata.toml`, or update the
existing chezmoi data for machine-specific `reposDir` settings.
The updater creates worktrees beside each clone, never in a global directory:
`<root>/<repo>.worktrees/<branch-slug>`. For example,
`~/Repos/dotfiles.worktrees/feat-repository-sync`. Development worktree
directories use a filesystem-safe version of their branch name (for example,
`feat/repository-sync` becomes `feat-repository-sync`). Recovery directories
start with `recovery-` followed by the branch name and a unique suffix (for
example, `recovery-feat-repository-sync-2026-11-01--07-00-00-abc123`).
The timestamp uses local time in `YYYY-MM-DD--HH-mm-ss` format. A recovery
of a detached checkout identifies its commit instead of claiming a branch.
Existing directories with the same slug receive a unique suffix rather than
being overwritten. For branch names consisting only of symbols, the name keeps
an escaped version of each character (for example, `+++` becomes
`branch-u2b-u2b-u2b`) rather than incorrectly using `detached`.

The managed [Worktrunk user configuration](../../home/dot_config/worktrunk/config.toml)
uses the same repository-sibling layout for new `wt switch` worktrees.
Agents should also use this directory for directly created Git worktrees.

The [LaunchAgent](../../home/private_Library/private_LaunchAgents/com.arthur.repo-refresh.plist.tmpl)
runs at login/load and once a minute while the Mac is awake. Runs do not overlap.
The [installation hook](../../home/run_after_25-ensure-repo-refresh.sh.tmpl) avoids
restarting active transactions. Scheduling changes to an already loaded service
take effect after logging out and back in.

## 🔄 What happens automatically

Each run follows this sequence:

1. **Fetch and resolve the default branch.** The remote decides whether that is
   `main`, `master`, or another name. Offline/authentication failures are reported
   and retried later, without requesting credentials interactively.
2. **Restore the permanent checkout.** When the permanent checkout is already
   on a clean default branch and can fast-forward, use `git merge --ff-only`
   without creating a redundant recovery worktree. Retain the preservation
   path for dirty or divergent checkouts, interrupted operations, submodules,
   sparse checkouts, and possible collisions with ignored files. In those
   cases, preserve the previous files, index and commits before force-restoring
   the fetched default commit. A displaced feature branch is checked out in
   a separate development worktree.
3. **Remove verified merged branches.** Before rebasing, verify integration
   using local Git history only, independently of GitHub or Bitbucket. A branch
   qualifies when its tip is an ancestor of the fetched remote default (but
   is not identical to the current default tip), or when its complete cumulative
   file changes exactly match a single commit in that
   default's first-parent history (a conservative squash-merge check). Commit
   messages never establish merge status. Delete an eligible local worktree and
   branch only when no tracked, untracked, or valuable ignored data would be
   lost. Known ignored build caches can be discarded. For a same-name remote
   branch, delete only when its tip matches the verified local tip, using a
   force-with-lease condition; preserve diverged or protected remote branches.
   Uncertain merges and dirty worktrees are reported and retained.
4. **Rebase remaining feature branches.** Rebase unmerged branches except
   `main`, `master`, and the actual default branch onto that commit. Use
   existing worktrees or create missing ones. Already-current branches need no
   rebase. Rebases remain local; only verified merged-branch cleanup deletes
   remote branches.

Linked worktrees are excluded from permanent-clone discovery, but their branches
still participate in cleanup and rebasing. Detached recovery copies are
retained separately, since they can contain unique uncommitted historical data.
If another linked worktree incorrectly holds the default branch, the updater
verifies that it belongs to the same repository and removes that specific
worktree with `git worktree remove --force --force`, including any uncommitted
changes even if it was locked. Other linked worktrees, including those under
`~/Tickets`, remain registered. A direct clone with a stale `core.worktree`
setting is repaired to use its own directory without resetting files at the old
path. Checkout identity checks use filesystem identity, not case-sensitive path
spelling, so `Repos`/`repos`, `Tickets`/`tickets`, and `third-party` path aliases
on case-insensitive Macs do not trigger unnecessary repairs. Different actual
working directories still fail the safety check. A newly created feature
branch without its own commits is not treated as merged, even if the default
branch advances before its first commit.

### Archived recoveries

With the Chezmoi-managed `"archiveRecoveries": true` configuration, each
scheduled run archives completed, detached recovery worktrees **after**
repository refresh and branch maintenance. The archive is outside the
repository root:

```text
~/Archives/repo-refresh/<repo>/<timestamp>-<id>/
├── gitdir/                 # Independent copy of the complete Git database and indices
├── recoveries/
│   └── recovery-<branch>-<timestamp>-<id>/  # All files, including ignored data
└── manifest.json           # Source paths, commit IDs, integrity checks and progress
```

The script first copies the Git database and *every* eligible recovery,
checks file contents, symlinks, modes, ownership, and extended attributes
(excluding `com.apple.provenance`, which macOS reassigns on copy), then verifies
`HEAD`, staged index entries, and Git status against the original.
Only when the **entire** batch passes validation does it unregister the
original worktrees. It uses `cp -pR` on macOS to preserve symlinks, ACLs,
extended attributes and resource forks. Unfinished, locked, actively rebasing,
unverified and ordinary development worktrees are not eligible for removal.
If an archive or verification fails, existing worktrees are retained.

To archive old recoveries without running a Git refresh:

```bash
repo-refresh --archive-recoveries --repository "$HOME/Repos/dotfiles"
```

Omit `--repository` to archive completed recoveries from every permanent
checkout in the configured repository root. Existing feature worktrees remain
registered and untouched.

Archived recoveries are still independently inspectable. Open a folder under
`~/Archives/repo-refresh/<repo>/<batch>/recoveries/<recovery-name>` in
VS Code, or use `git -C <archived-recovery-path> status`,
`git -C <archived-recovery-path> log` and
`git -C <archived-recovery-path> show :file` to inspect staged files.
The archive contains its own Git database so the live repository does not
need to retain the detached recovery worktree or its metadata. Keep these
archives as long as their history or local changes may be needed; no automatic
retention/deletion policy is applied.

### Branch outcomes

Use `repo-refresh --status` to find each branch's state and relevant paths:

| State | What happened | Next action |
| --- | --- | --- |
| `current` | Already contains the refreshed default commit. | None. |
| `merged-cleaned` | Git verified a merged or exact squash-equivalent branch. | Local branch/worktree removed; check the remote-deletion result. |
| `merged-protected` | A merged branch has uncommitted data or an unverified worktree path. | Inspect it manually; no automatic rebase or deletion occurs. |
| `rebased` | Rebase succeeded; Git restored tracked edits where possible. | Continue in the reported worktree. |
| `conflicts` | Replaying commits or restoring edits exposed conflicts. | Resolve them there; later runs leave them alone. |
| `in-progress` | A Git operation is unfinished. | Finish or abort it; later runs do not restart it. |
| `edits-pending` | The branch was updated, but Git could not restore all edits. | Recover edits from the reported backup or saved stash. |
| `failed` | Preservation or rebasing could not complete. | Inspect the failed worktree and its saved recovery; the updater does **not** retry this branch automatically. |

**Automatic rebases rewrite local commit IDs and change development-worktree
files.** Avoid concurrent editing during a scheduled rebase. Conflicts are an
expected outcome, not a reason to discard work or abort the rebase.

## 🛟 Inspect and recover work

Find the latest run or trigger one immediately:

```sh
repo-refresh --status
repo-refresh
```

The reported paths distinguish the places you may need:

| Location | Contents |
| --- | --- |
| Permanent checkout | The fetched default branch. |
| Branch worktree | The rebased branch or visible unresolved conflicts. |
| Recovery worktree | Files and index from before replacement or rebase. |
| Protected `refs/repo-refresh/` refs | Previous commits and separately retained edit stashes. |

### Retry a failed permanent checkout

Before allocating a recovery, the updater writes `repo-refresh-checkout.json`
inside the checkout's Git directory. A failed or interrupted attempt is not
repeated while the checkout state, index, active operation, and upstream target
remain unchanged. This includes incomplete backup copies. Nested linked worktrees
are rejected before files are copied, and the existing free-space check still
applies.

Inspect the failure and any recovery first. After correcting its cause, explicitly
acknowledge the attempt by removing only the retry record:

```sh
cd ~/Repos/example
rm -- "$(git rev-parse --git-path repo-refresh-checkout.json)"
```

A changed checkout or upstream target permits another attempt after a recorded
failure. An interrupted attempt always requires acknowledgement because its
last completed operation is unknown.
Existing recoveries remain intact; archival moves them out of Git's worktree list
but does not reduce total disk usage. This guard prevents duplicate retries of
unchanged permanent-checkout state; it is not a retention policy or an incremental
backup system. Feature-branch backup failures also use the existing failed-rebase
record, so a copy failure cannot bypass its manual retry requirement.

### Resolve a branch conflict

Work in the branch worktree from status:

1. Inspect `git status` and edit the conflicted files.
2. Stage the resolutions with `git add`.
3. For an active rebase, run `git rebase --continue`. For edit-restoration conflicts
   after the rebase finished, resolve and commit the edits normally.

### Recover older files or pending edits

Use the recovery path from status. To locate older copies and their records:

```sh
git worktree list
git -C /path/to/recovery status
git -C /path/to/recovery rev-parse --git-path repo-refresh/recovery.json
git -C /path/to/branch-worktree rev-parse --git-path repo-refresh-rebase.json
```

The rebase record identifies the pre-rebase copy and any saved edit stash. After
recovering an `edits-pending` result, remove that branch's `repo-refresh-rebase.json`
record to acknowledge recovery and allow future rebases.

Recovery copies are private and **never automatically deleted**. Backups retain
tracked edits, staged state, untracked files, and ignored data, **except**
confirmed ignored build directories `node_modules`, `.next`, and `out`, which
are regenerable and excluded to prevent duplicating hundreds of megabytes per
recovery. Git-tracked content in these directories is never excluded. Before
creating a recovery, at least 2 GiB of additional free disk space must remain.

After investigating a `failed` rebase, resolve the problem and explicitly
remove that worktree's `repo-refresh-rebase.json` marker to permit another
attempt; until then the updater will report the failure without retrying.

Do not put unrelated clones inside `<repo>.worktrees`; they belong in a
separate repository directory. Existing worktrees created by external agents
are reusable by the updater, but those agents must also follow this convention
for new worktrees. They may contain
ignored credentials and large build directories. Keep what you need before
explicitly removing old worktrees and their protected refs. Status shows the
latest run; `git worktree list` also lists older copies.

## 🧪 Implementation and verification

The [updater](../../home/dot_local/bin/executable_repo-refresh) preserves staged
versus unstaged changes, untracked and ignored files, symlinks, executable modes,
conflicted indexes, and previous commits. Submodule copies receive independent
Git metadata. Interrupted-operation metadata is saved as evidence; archived
operations are not automatically resumed in recovery copies.

Preservation failure prevents destructive replacement or rebase. Locks,
filesystem failures, nested linked worktrees, special files, and files observed
changing during copying can prevent preservation. Failure after preservation
leaves its recovery copy available. Ignored files remain in the permanent
checkout where possible and are also copied to recovery.

**The managed root is automatically replaceable.** Edit in development worktrees.
Editors and agents do not obey the updater's locks: change detection reduces
races, but cannot guarantee preservation of a save made after the final check.
The same limitation applies to concurrent writes during branch rebases.

Run real local-Git scenarios and isolated installation/reapply checks:

```sh
.venv/bin/pytest -q tests/integration/test_repo_refresh.py
```

Tests use disposable repositories and local remotes. The real macOS scheduler
test runs only on ephemeral CI, never against the developer's repositories.
