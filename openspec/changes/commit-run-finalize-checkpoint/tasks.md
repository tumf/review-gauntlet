## Implementation Tasks

- [x] Add a checkpoint-only git commit helper for run finalization. (verification: unit - tests exercise committed, no-op, blocked, and git-failure result branches without staging non-checkpoint paths)
- [x] Wire `RunController.run()` or the run CLI integration so successful finalization invokes the checkpoint commit helper before returning the completed run result. (verification: integration - `uv run pytest tests/test_run_controller.py` proves a run that removes the active session marker attempts checkpoint commit handling)
- [x] Restrict staging to `.review-gauntlet/checkpoints/latest` and concrete generated checkpoint files while rejecting or surfacing unrelated dirty worktree state. (verification: integration - `uv run pytest tests/test_cli.py` or dedicated run/finalize tests prove unrelated dirty files remain unstaged/uncommitted and appear as a visible blocker)
- [x] Return structured checkpoint commit metadata in `run` results for committed, no-op, blocked, and failed states. (verification: integration - focused CLI tests parse JSON output from `review-gauntlet run --format json` and assert fields such as `checkpoint_commit_attempted`, `checkpoint_committed`, `checkpoint_commit`, and `checkpoint_commit_reason`)
- [x] Preserve standalone `review-gauntlet finalize` and `finalize --merge` behavior. (verification: integration - existing finalize and git-worktree merge tests continue to pass, and added tests prove the new helper is only invoked for normal run finalization)
- [x] Update OpenSpec requirements and scenarios for run post-finalize checkpoint commit behavior. (verification: integration - `cflx openspec validate commit-run-finalize-checkpoint --strict` passes)
- [x] Run focused and full project quality gates after implementation. (verification: integration - `uv run pytest tests/test_run_controller.py tests/test_cli.py` and `make check` pass, or unrelated failures are documented with evidence)

## Future Work

- Add optional user configuration for disabling automatic checkpoint commits only if a later workflow needs it.
- Add remote push or PR integration only as a separate proposal if requested.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate commit-run-finalize-checkpoint --archive-gate`

## Acceptance #1 Failure Follow-up
- [x] BLOCKER: commit_latest_checkpoint never commits real checkpoint artifacts — fixed by allowing concrete generated checkpoint artifacts under `.review-gauntlet/checkpoints/<checkpoint_id>/` and by resolving the current `latest` pointer to its real checkpoint directory.
- [x] FALSE ASSURANCE: no test exercises the real write_latest_checkpoint→commit_latest_checkpoint flow — fixed by adding a regression test that writes the real checkpoint layout with `write_latest_checkpoint` and verifies `commit_latest_checkpoint` commits the pointer plus generated checkpoint files.
- [x] SECONDARY: generated_files is parsed from the agent's stdout JSON and may be empty — fixed by making `commit_latest_checkpoint` derive allowed generated files from the `latest` checkpoint pointer when explicit generated files are absent or incomplete.
