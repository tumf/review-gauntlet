## Implementation Tasks

- [x] Refactor `src/review_gauntlet/cli.py` review result persistence so `_cmd_review` can persist each successful `ReviewAdapterResult` as soon as it is observed instead of waiting for every selected cell to finish. (verification: unit - add or update `tests/test_cli_session_review.py` coverage around `review_cells_concurrently` and persistence helpers to show a completed cell is marked reviewed before remaining cells complete)
- [x] Add interrupt-time draining in `src/review_gauntlet/cli.py` for already-completed futures, ensuring `future.done()` outcomes are collected without blocking before unfinished futures are cancelled. (verification: unit - add a deterministic fake adapter/future scenario in `tests/test_review_progress.py` proving completed futures are recorded and unfinished futures are not awaited)
- [x] Keep unfinished, cancelled, and failed-during-interrupt cells pending while preserving the active session in `SessionStore`. (verification: integration - add a CLI test in `tests/test_review_progress.py` or `tests/test_cli_session_review.py` that inspects `SessionStore.list_cells(...)` after simulated interrupt and observes reviewed/pending split plus existing active session)
- [x] Persist findings and finding occurrences for successful cells from an interrupted run using the same normalization path as a normal review run. (verification: integration - add a fixture-backed interrupted review test in `tests/test_cli_session_review.py` that queries `findings` and `finding_occurrences` rows in `.review-gauntlet/ledger.sqlite`)
- [x] Verify resume behavior after interruption selects only remaining pending cells. (verification: integration - add a CLI test in `tests/test_cli_session_review.py` that runs `review` again after an interrupted run and asserts already reviewed cells are not selected or reprocessed)
- [x] Run repository checks. (verification: integration - `make check`)

## Future Work

- Optional migration or repair command for runs interrupted by versions that did not persist completed artifacts is intentionally deferred.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate preserve-interrupted-review-results --archive-gate`
