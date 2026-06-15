## Implementation Tasks

- [ ] Add CLI flags and preserve existing target semantics. Completion condition: `review-gauntlet init --help` exposes `--git-worktree`, `review-gauntlet finalize --help` exposes `--merge`, and `--worktree` continues to select workspace-diff targets. (verification: unit - update `tests/test_cli.py` and `tests/test_init_targets.py` to assert parser help and target metadata for `--worktree`, `--git-worktree`, and combined usage.)

- [ ] Implement session Git metadata modeling and persistence. Completion condition: sessions created with `--git-worktree` persist `git_worktree.enabled`, `base_branch`, `base_commit`, `session_branch`, and `worktree_path` in session metadata without requiring a ledger schema migration. (verification: integration - a temporary Git repository test reads `SessionStore.session_metadata()` after `init --git-worktree` and validates every metadata field resolves to the expected local Git objects/paths.)

- [ ] Implement safe session branch and linked worktree creation. Completion condition: `init --git-worktree` creates a unique path-safe branch under `review-gauntlet/`, creates a linked worktree under `.review-gauntlet/worktrees/<session-id>/`, and reports structured branch/worktree evidence in command output. (verification: integration - add tests that run `git branch --list`, `git worktree list --porcelain`, and filesystem checks after `main(["init", ..., "--git-worktree", "--format", "json"])`.)

- [ ] Ensure `--worktree` target selection composes with Git worktree isolation. Completion condition: `init --worktree --git-worktree` records a workspace-diff target while also creating Git-worktree metadata and does not reinterpret `--worktree` as linked-worktree creation. (verification: integration - update or add `tests/test_init_targets.py` cases asserting `metadata["target"]["kind"] == "worktree"` and `metadata["git_worktree"]["enabled"] is True`.)

- [ ] Add merge preflight validation for `finalize --merge`. Completion condition: merge is blocked before checkpoint writes or branch mutation when the active session is not Git-worktree-backed, the base branch/session branch/session worktree is missing, the base branch has dirty files, the base branch has advanced from `base_commit`, or the merge would conflict. (verification: integration - add local Git repository tests covering each blocker and asserting structured `can_finalize: false`, `merged: false`, preserved active session marker, and retained session branch/worktree.)

- [ ] Implement checkpoint commit behavior for Git-worktree finalize. Completion condition: after existing finalize gates pass, `finalize --merge` writes checkpoint artifacts, stages intended session changes including generated checkpoint files, and creates a deterministic session-branch commit before merge. (verification: integration - a test completes a session, runs `finalize --merge --format json`, and asserts the session branch history or merge result contains a commit whose tree includes `.review-gauntlet/checkpoints/latest` and generated checkpoint files.)

- [ ] Implement merge into recorded base branch. Completion condition: successful `finalize --merge` merges the committed session branch into `base_branch`, records `merged: true`, `base_branch`, `session_branch`, and `merge_commit`, and leaves the base branch at a commit containing the session branch changes. (verification: integration - a temporary Git repository test asserts `git rev-parse <base_branch>` equals the reported merge commit and `git merge-base --is-ancestor <session_commit> <base_branch>` succeeds.)

- [ ] Implement post-merge cleanup of session worktree and branch. Completion condition: after successful merge, the active session marker is removed, the session state is finalized, `git worktree remove <worktree_path>` succeeds, `git branch -d <session_branch>` succeeds, and output includes `cleaned_up: true`, removed worktree path, and deleted branch. (verification: integration - assert the worktree path no longer exists, `git branch --list <session_branch>` is empty, and subsequent `status` without a new `init` fails with the existing actionable no-active-session message.)

- [ ] Handle cleanup failure after successful merge without hiding merge success. Completion condition: if worktree removal or branch deletion fails after merge, the command reports `merged: true`, `cleaned_up: false`, `cleanup_blockers`, and `next_required_action: cleanup_git_worktree` while keeping the finalized session state. (verification: unit/integration - monkeypatch Git cleanup helper failure or construct a local condition that prevents deletion, then assert output and finalized ledger state.)

- [ ] Update documentation and examples. Completion condition: README/basic usage documents `init --git-worktree`, `finalize --merge`, the difference between `--worktree` and `--git-worktree`, and cleanup behavior after merge. (verification: manual - review README snippets; unit - help text assertions cover option wording.)

- [ ] Run project verification. Completion condition: all repository checks pass after implementation. (verification: manual - run `make check` and record the result in implementation notes or PR evidence.)

## Future Work

- Automatic rebase or refresh when the recorded base branch has advanced.
- Remote push / pull request creation for merged or review branches.
- A dedicated cleanup command for failed post-merge cleanup remnants, if cleanup failures prove common.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-git-worktree-session-finalize --archive-gate`
