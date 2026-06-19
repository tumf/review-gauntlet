## Implementation Tasks

- [x] Add repeatable `--cell` parsing to the `review` subcommand in `src/review_gauntlet/cli.py`. Completion condition: `argparse` stores zero or more requested cell IDs without changing existing `review` invocations. (verification: unit - parser/CLI tests in `tests/test_cli.py` or `tests/test_cli_session_review.py` exercise `review --cell RGC-example` and a no-selector invocation.)
- [x] Validate requested cell IDs against the reconciled current active-session cell universe before creating a run or invoking an adapter. Completion condition: unknown requested IDs produce usage-error exit semantics, name the unknown IDs, and leave run/adaptor artifacts unchanged. (verification: integration - add `tests/test_cli_session_review.py::test_review_rejects_unknown_cell_selector`, calling `main(["review", tmp_path, "--cell", "RGC-missing", "--fixture", fixture, "--format", "json"])`, asserting exit code `64`, no adapter fixture effect, and no new run row via `SessionStore`.)
- [x] Filter selected review cells by requested cell IDs after normal pending-state eligibility is computed, with deterministic de-duplication. Completion condition: duplicate requested IDs and multiple requested IDs result in at most one adapter invocation per matching pending cell, sorted by existing review selection order. (verification: integration - add `tests/test_cli_session_review.py::test_review_cell_selector_reviews_unique_pending_subset`, using fixture-backed `main([... "review", "--cell", first_id, "--cell", first_id, "--cell", second_id, ...])` and asserting `reviewed_cells == 2` plus persisted `SessionStore.list_cells()` states.)
- [x] Preserve already-reviewed cell handling under explicit selection. Completion condition: requesting a cell that is already `REVIEWED` does not invoke the adapter for that cell, does not regress its state, and reports the normal zero-selected/no-op review output when no requested pending cells remain. (verification: integration - add `tests/test_cli_session_review.py::test_review_cell_selector_skips_already_reviewed_cell`, first reviewing one fixture-backed cell, then rerunning `main(["review", tmp_path, "--cell", same_id, "--fixture", fixture, "--format", "json"])` and asserting `reviewed_cells == 0` with stable `SessionStore.list_cells()` coverage.)
- [x] Preserve compatibility of `--budget`, `--parallel`, JSON output, and no-selector behavior. Completion condition: existing review tests still pass, and targeted selection respects `--budget` after selector filtering without changing parseable status shape. (verification: integration - update/add tests around `tests/test_cli_session_review.py` or `tests/test_review_progress.py`; final command `make check` passes.)

## Future Work

- Consider separate selectors for file paths, rule IDs, slice IDs, or state filters if users need broader targeting than explicit cell IDs.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-review-cell-selection --archive-gate`
