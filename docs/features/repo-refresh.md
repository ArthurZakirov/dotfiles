# 🔄 Keep repositories and feature branches current

[← Feature index](README.md) · [Dotfiles setup](../setup.md)

`repo-refresh` keeps permanent clones on the latest remote default branch and
rebases local feature branches onto it. It preserves recovery copies before
rewriting work and leaves conflicts visible for you to resolve.

## ⚙️ Install and configure

Use the normal dotfiles installation flow:

1. **Review the defaults** in the
   [initial configuration](../../home/dot_config/repo-refresh/create_private_config.json.tmpl).
   Both Mac installations use the same defaults. The updater starts **disabled**;
   enable it explicitly in the local configuration only after checking available
   disk space and any unresolved branches.
2. **Follow the [setup guide](../setup.md)** to preview and apply the changes.
   To override defaults before the first run, create the local JSON configuration
   at the path below before applying. Otherwise, chezmoi creates it for you.
3. **Adjust local settings as needed.** Later dotfiles applies preserve this file.

   ```sh
   code ~/.config/repo-refresh/config.json
   ```

The configuration fields define the managed scope:

| Field | What to set |
| --- | --- |
| `root` | Directory containing permanent clones directly (no nested repository groups). |
| `remote` | Remote whose advertised default branch should be followed. |
| `enabled` | `false` pauses future runs; an active run finishes normally. |

The root is set during chezmoi initialization via `REPOS_DIR` (saved as
`reposDir` in the local chezmoi configuration; default:
`~/Repos`), used by the shell and the initial repo-refresh configuration.
The local `~/.config/repo-refresh/config.json` can override it afterward.
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
2. **Restore the permanent checkout.** Preserve its previous files, index and
   commits, then force it onto the fetched default commit—even after divergence,
   a force-push, or an interrupted Git operation. A displaced feature branch is
   checked out in a separate development worktree.
3. **Remove verified merged branches.** Before rebasing, verify integration
   using local Git history only, independently of GitHub or Bitbucket. A branch
   qualifies when its tip is an ancestor of the fetched remote default, or when
   its complete cumulative file changes exactly match a single commit in that
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
If another worktree holds the default branch, it is detached at its existing
commit without changing its files or index.

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
