## Implementation Tasks

- [x] Restore safe latest-pointer fallback in checkpoint commit allowlisting so `commit_latest_checkpoint()` includes the current latest checkpoint directory's `status.json`, `findings.json`, `events.json`, and `summary.md` when `generated_files` is empty or incomplete. (verification: unit - `uv run pytest tests/test_checkpoint_commit.py::test_commit_latest_checkpoint_commits_real_layout_with_empty_generated_files`)
- [x] Preserve path-safety hardening by refusing fallback allowlisting when `.review-gauntlet/checkpoints/latest` is missing, a directory, a symlink, references an unsafe checkpoint id, or points outside the standard checkpoint directory layout. (verification: unit - targeted invalid-pointer cases in `tests/test_checkpoint_commit.py`)
- [x] Keep stale or unrelated checkpoint artifacts outside the current latest checkpoint directory blocked as `blocked_by_non_checkpoint_changes`. (verification: unit - `uv run pytest tests/test_checkpoint_commit.py::test_commit_latest_checkpoint_blocks_stale_checkpoint_artifacts_not_generated`)
- [x] Add run-level regression coverage proving an agent step that finalizes the active session and emits non-JSON stdout still commits the generated checkpoint artifacts and reports `checkpoint_committed: true`. (verification: integration - targeted test in `tests/test_run_controller.py` or `tests/test_cli_run.py`)
- [x] Verify standalone finalize and merge-finalize semantics are unchanged by the fallback. (verification: integration - existing finalize and git-worktree tests plus any required targeted assertions)
- [x] Run project checks after implementation. (verification: integration - `make check`)

## Future Work

- Add optional user configuration for disabling automatic checkpoint commits only if a later workflow needs it.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate fix-run-finalize-checkpoint-commit --archive-gate`
