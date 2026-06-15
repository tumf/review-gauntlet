# Design: Git worktree-backed review sessions

## Requested Artifact

Implementation proposal with spec deltas, runtime Git workflow changes, tests, and documentation updates.

## Goals

- Isolate each review session in its own Git branch and linked worktree when requested.
- Preserve the existing `--worktree` review-target meaning.
- Make `finalize --merge` a complete success-path operation: checkpoint, commit, merge, finalize, remove worktree, delete branch.
- Keep all completion blockers explicit and prevent merge/cleanup from masking incomplete coverage, live findings, dirty state, or failed verification.

## Non-goals

- No remote Git provider operations.
- No automatic conflict resolution.
- No automatic rebase when the base branch advances.
- No cleanup of branches or worktrees that are not recorded in session metadata.

## CLI model

### `init --git-worktree`

`--git-worktree` is an execution-isolation flag, not a target-selection flag. It can be used with any existing target mode:

- `init --git-worktree`: default target selection plus isolated session worktree.
- `init --worktree --git-worktree`: workspace-diff target plus isolated session worktree.
- `init --from main --to HEAD --git-worktree`: branch/range target plus isolated session worktree.

The existing `--worktree` flag keeps its current meaning: review staged, unstaged, and untracked workspace changes.

### `finalize --merge`

`--merge` requests the Git-worktree completion path. It should block for non-Git-worktree sessions with structured output rather than silently performing plain finalize.

## Durable state

Session metadata should include a `git_worktree` object:

```json
{
  "enabled": true,
  "base_branch": "main",
  "base_commit": "<resolved sha>",
  "session_branch": "review-gauntlet/RGS-abc123456789",
  "worktree_path": ".review-gauntlet/worktrees/RGS-abc123456789"
}
```

The implementation should avoid a SQLite schema migration unless stronger querying is required. Existing JSON metadata is sufficient for the first implementation.

## Worktree creation sequence

1. Resolve repository root and verify the root is a Git repository with a resolvable `HEAD`.
2. Resolve the current branch name for `base_branch`; detached HEAD should be rejected unless a future design adds explicit support.
3. Record `base_commit` as the resolved current `HEAD`.
4. Generate the session id before branch/worktree creation.
5. Create a path-safe session branch name, for example `review-gauntlet/<session-id>`.
6. Create a linked worktree under `.review-gauntlet/worktrees/<session-id>/` checked out to the session branch.
7. Create the session ledger and active marker in the session worktree root.
8. Return structured output including branch/worktree metadata.

The worktree path should be relative in output when possible but stored in a form that can be resolved safely from the repository root.

## Finalize merge sequence

`finalize --merge` should proceed in ordered phases:

1. Load active session metadata and validate `git_worktree.enabled`.
2. Run all existing finalize blockers before making merge-side effects.
3. Run merge preflight checks:
   - base branch exists
   - session branch exists
   - session worktree exists and is associated with the session branch
   - base branch worktree is clean
   - base branch still points at `base_commit`
   - merge can be performed without conflict
4. Write checkpoint artifacts using the existing checkpoint writer.
5. Stage intended session changes and create a session checkpoint commit.
6. Merge the session branch into the recorded base branch.
7. Mark the session finalized and clear active session marker.
8. Remove the session worktree.
9. Delete the session branch.
10. Return structured merge and cleanup evidence.

## Commit policy

For Git-worktree sessions, `finalize --merge` must create a commit because merge requires committed state. The commit should include generated checkpoint artifacts and intended session branch changes. The implementation should avoid committing ignored files or files outside the repository.

A deterministic commit message is recommended:

```text
Finalize review-gauntlet session <session-id>
```

The implementation may include checkpoint id and generated file list in the commit body.

## Merge policy

The first implementation should block if the recorded base branch has moved from `base_commit`. This keeps behavior deterministic and avoids hidden rebase/merge complexity.

A successful merge may be fast-forward or produce a merge commit depending on implementation strategy, but output must report the resulting base branch commit as `merge_commit` and prove the session changes are reachable from the base branch.

## Cleanup policy

Cleanup is attempted only after merge succeeds.

- Worktree removal comes before branch deletion because Git will reject branch deletion while it is checked out in a linked worktree.
- Cleanup operates only on the recorded `worktree_path` and `session_branch`.
- Merge blockers never remove the worktree or branch.
- Cleanup failure after merge does not undo merge. It reports `cleaned_up: false`, records blockers, and uses `next_required_action: cleanup_git_worktree`.

## Output model

Successful `finalize --merge` should extend existing finalize output with fields such as:

```json
{
  "merged": true,
  "cleaned_up": true,
  "base_branch": "main",
  "session_branch": "review-gauntlet/RGS-abc123456789",
  "merge_commit": "<sha>",
  "removed_worktree_path": ".review-gauntlet/worktrees/RGS-abc123456789",
  "deleted_branch": "review-gauntlet/RGS-abc123456789"
}
```

Blocked merge output should include `merged: false`, `cleaned_up: false`, `finalize_blockers`, and a `next_required_action` describing the next repair step.

## Verification strategy

Use local temporary Git repositories in tests so no external systems or credentials are required. Integration tests should verify real `git branch`, `git worktree`, `git merge-base`, and filesystem outcomes. Unit tests should cover helper error normalization and output shaping where full Git state would be unnecessarily expensive.
