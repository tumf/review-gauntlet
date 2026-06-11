## Implementation Tasks

- [ ] Update review cell ledger identity to be session-scoped. Completion condition: `src/review_gauntlet/session_store.py` creates `review_cells` with `primary key (session_id, cell_id)` while keeping the stored `cell_id` value unchanged. (verification: unit - extend `tests/test_session_store.py` to create two sessions containing `ReviewCell(id="RGC-1", ...)` without an integrity error and assert both rows exist under different `session_id` values.)

- [ ] Qualify review cell state updates by session. Completion condition: `SessionStore.update_cell_state` accepts `session_id`, updates with `where session_id = ? and cell_id = ?`, and no production caller updates coverage by `cell_id` alone. (verification: unit - add a `tests/test_session_store.py` case where two sessions share `RGC-1`, updating one session leaves the other session's row unchanged.)

- [ ] Wire session-scoped updates through CLI review reconciliation. Completion condition: all calls in `src/review_gauntlet/cli.py` that mark cells `reviewed`, `stale`, or `superseded` pass the active session ID associated with the current command. (verification: integration - extend `tests/test_cli_session_review.py` or `tests/test_init_targets.py` to run repeated `init` modes with overlapping cells, then run `uv run review-gauntlet status --format json` and assert coverage belongs to the active session.)

- [ ] Preserve deterministic prompt-visible review cell IDs. Completion condition: `src/review_gauntlet/review_cells.py` keeps `cell_id_for()` behavior and existing adapter prompt/fixture tests continue to use the same `RGC-...` IDs. (verification: unit - existing `tests/test_review_cells.py` and `tests/test_review_prompts.py` continue to pass without snapshot changes to the ID format.)

- [ ] Add a regression covering repeated initialization without migration behavior. Completion condition: a test creates a fresh repo, runs `review-gauntlet init`, then `review-gauntlet init --all`, and asserts the second command succeeds; the test does not depend on migrating an old-schema database. (verification: integration - add or extend `tests/test_init_targets.py` or `tests/test_cli_session_review.py` with the two-command scenario.)

- [ ] Run project checks. Completion condition: formatting, lint, typecheck, and tests all pass with the repository's CI-equivalent command. (verification: integration - `make check`.)

## Future Work

- If old ledgers need to be preserved later, create a separate migration or repair proposal. This change intentionally excludes migration support.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate fix-review-cell-session-scope --archive-gate`
