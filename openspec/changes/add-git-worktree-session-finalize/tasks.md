## Implementation Tasks

- [x] Add CLI flags and preserve existing target semantics. Completion condition: `review-gauntlet init --help` exposes `--git-worktree`, `review-gauntlet finalize --help` exposes `--merge`, and `--worktree` continues to select workspace-diff targets. (verification: unit - update `tests/test_cli.py` and `tests/test_init_targets.py` to assert parser help and target metadata for `--worktree`, `--git-worktree`, and combined usage.)

- [x] Implement session Git metadata modeling and persistence. Completion condition: sessions created with `--git-worktree` persist `git_worktree.enabled`, `base_branch`, `base_commit`, `session_branch`, and `worktree_path` in session metadata without requiring a ledger schema migration. (verification: integration - `tests/test_git_worktree_session.py::test_init_git_worktree_records_metadata_and_preserves_worktree_target` reads `SessionStore.session_metadata()` after `init --git-worktree` and validates every metadata field against Git objects/paths created by `src/review_gauntlet/git_worktree.py::create_session_worktree`.)

- [x] Implement safe session branch and linked worktree creation. Completion condition: `init --git-worktree` creates a unique path-safe branch under `review-gauntlet/`, creates a linked worktree under `.review-gauntlet/worktrees/<session-id>/`, and reports structured branch/worktree evidence in command output. (verification: integration - `tests/test_git_worktree_session.py::test_init_git_worktree_records_metadata_and_preserves_worktree_target` asserts `git branch --list`, filesystem worktree existence, JSON output metadata, and `src/review_gauntlet/git_worktree.py::create_session_worktree` path/branch construction.)

- [x] Ensure `--worktree` target selection composes with Git worktree isolation. Completion condition: `init --worktree --git-worktree` records a workspace-diff target while also creating Git-worktree metadata and does not reinterpret `--worktree` as linked-worktree creation. (verification: integration - update or add `tests/test_init_targets.py` cases asserting `metadata["target"]["kind"] == "worktree"` and `metadata["git_worktree"]["enabled"] is True`.)

- [x] Add merge preflight validation for `finalize --merge`. Completion condition: merge is blocked before checkpoint writes or branch mutation when the active session is not Git-worktree-backed, the base branch/session branch/session worktree is missing, the base branch has dirty files, the base branch has advanced from `base_commit`, or the merge would conflict. (verification: integration - `tests/test_git_worktree_session.py::test_finalize_merge_blocks_non_git_worktree_session`, `::test_finalize_merge_blocks_when_base_branch_advanced_before_checkpoint`, `::test_merge_preflight_reports_missing_and_dirty_base_blockers`, and `::test_merge_preflight_reports_conflict_without_mutating_session` cover blockers and preservation; implementation is `src/review_gauntlet/git_worktree.py::merge_preflight_blockers`.)

- [x] Implement checkpoint commit behavior for Git-worktree finalize. Completion condition: after existing finalize gates pass, `finalize --merge` writes checkpoint artifacts, stages intended session changes including generated checkpoint files, and creates a deterministic session-branch commit before merge. (verification: integration - `tests/test_git_worktree_session.py::test_finalize_merge_commits_merges_and_cleans_up` completes a session and runs `finalize --merge --format json`; checkpoint copy/staging is implemented by `src/review_gauntlet/cli.py::_copy_checkpoint_artifacts_to_session_worktree` and `src/review_gauntlet/git_worktree.py::_commit_session_changes`.)

- [x] Implement merge into recorded base branch. Completion condition: successful `finalize --merge` merges the committed session branch into `base_branch`, records `merged: true`, `base_branch`, `session_branch`, and `merge_commit`, and leaves the base branch at a commit containing the session branch changes. (verification: integration - `tests/test_git_worktree_session.py::test_finalize_merge_commits_merges_and_cleans_up` asserts `git rev-parse <base_branch>` equals reported `merge_commit` and `git merge-base --is-ancestor <session_commit> <base_branch>` succeeds; implementation is `src/review_gauntlet/git_worktree.py::merge_session_worktree`.)

- [x] Implement post-merge cleanup of session worktree and branch. Completion condition: after successful merge, the active session marker is removed, the session state is finalized, `git worktree remove <worktree_path>` succeeds, `git branch -d <session_branch>` succeeds, and output includes `cleaned_up: true`, removed worktree path, and deleted branch. (verification: integration - `tests/test_git_worktree_session.py::test_finalize_merge_commits_merges_and_cleans_up` asserts worktree removal, branch deletion, checkpoint presence, and active-session marker removal; implementation is `src/review_gauntlet/git_worktree.py::cleanup_session_worktree`.)

- [x] Handle cleanup failure after successful merge without hiding merge success. Completion condition: if worktree removal or branch deletion fails after merge, the command reports `merged: true`, `cleaned_up: false`, `cleanup_blockers`, and `next_required_action: cleanup_git_worktree` while keeping the finalized session state. (verification: unit/integration - `tests/test_git_worktree_session.py::test_finalize_merge_reports_cleanup_failure_after_success` monkeypatches `src/review_gauntlet/git_worktree.py::cleanup_session_worktree` failure and asserts output plus finalized ledger state.)

- [x] Update documentation and examples. Completion condition: README/basic usage documents `init --git-worktree`, `finalize --merge`, the difference between `--worktree` and `--git-worktree`, and cleanup behavior after merge. (verification: manual/unit - `README.md` documents the workflow and cleanup behavior; `tests/test_cli.py::test_cli_init_help_shows_boolean_defaults` and `::test_cli_finalize_help_exposes_merge` assert help wording.)

- [x] Run project verification. Completion condition: all repository checks pass after implementation. (verification: manual - run `make check` and record the result in implementation notes or PR evidence.)

## Future Work

- Automatic rebase or refresh when the recorded base branch has advanced.
- Remote push / pull request creation for merged or review branches.
- A dedicated cleanup command for failed post-merge cleanup remnants, if cleanup failures prove common.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-git-worktree-session-finalize --archive-gate`

## Acceptance Notes

Acceptance #1 flagged archive-gate evidence issues. The active implementation tasks above now cite repository-verifiable source paths, test cases, and runnable validation evidence; final OpenSpec validation remains in the non-checkbox `## Final Validation` section.
