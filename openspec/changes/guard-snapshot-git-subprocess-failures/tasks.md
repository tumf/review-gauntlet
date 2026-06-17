## Implementation Tasks

- [x] Handle `OSError` in `_finalize_reasons()` git cleanliness checks so they produce a conservative finalize blocker instead of raising. Completion condition: `_finalize_reasons()` catches `OSError` from `assert_review_universe_clean()` and `classify_working_tree_dirty()` and appends a resource-exhaustion blocker string; no `OSError` escapes into callers. (verification: unit - `tests/test_cli.py` or `tests/test_cli_session_review.py` monkeypatches `checkpoint._git` or `subprocess.run` to raise `OSError(errno.EMFILE, ...)` during finalize-reasons and asserts the returned list contains a structured blocker rather than raising.)

- [x] Guard `RunController.snapshot()` readiness calculation against `OSError` so TUI refresh does not crash. Completion condition: `snapshot()` catches `OSError` from `_ready_prompt()` or `_status_snapshot()` and produces a snapshot with `next_ready_prompt=None` or a blocked-state indicator instead of propagating the exception. (verification: unit - `tests/test_run_controller.py` injects a readiness-path `OSError(errno.EMFILE, ...)` and asserts `snapshot()` returns a non-None `RunSnapshot` without raising.)

- [x] Ensure `review-gauntlet status --format json` does not crash when finalize-blocker git subprocess startup fails. Completion condition: the status command returns structured JSON including a resource-exhaustion finalize blocker instead of a raw traceback. (verification: integration - `tests/test_cli.py` or a new status test monkeypatches `subprocess.run` for git calls and asserts parseable JSON output with a blocker.)

- [x] Ensure `review-gauntlet finalize` remains safe under subprocess startup `EMFILE`. Completion condition: `finalize` exits non-zero with structured blockers and does not write any checkpoint files when git cleanliness cannot be verified. (verification: integration - `tests/test_cli.py` or `tests/test_checkpoint_commit.py` monkeypatches git subprocess to raise `EMFILE` and asserts no checkpoint files are created and the output includes a structured blocker.)

- [x] Verify existing snapshot, status, and finalize behavior remains unchanged when git commands succeed. Completion condition: pre-existing TUI, status, and finalize tests pass without expected-output churn unrelated to the new blocker text. (verification: integration - `make check` passes.)

## Future Work

- Consider a separate proposal to add a TUI banner or status indicator when resource exhaustion is detected during dashboard refresh so the developer sees the issue without scrolling logs.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate guard-snapshot-git-subprocess-failures --archive-gate`
