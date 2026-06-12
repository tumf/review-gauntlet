## Implementation Tasks

- [ ] Refactor `src/review_gauntlet/cli.py` review result handling so successful `ReviewAdapterResult` entries are normalized, recorded, and marked reviewed before any failed run exits. (verification: integration - `tests/test_cli_session_review.py` simulates one failed selected cell followed by successful selected cells and asserts the successful cells are reviewed)
- [ ] Preserve failed-cell visibility by returning non-zero when any selected cell fails and including `failed_cell_id`, `error`, `failure`, current `coverage`, and the persisted `reviewed_cells` count in the final output. (verification: integration - `tests/test_cli_session_review.py` asserts `SystemExit(1)`, parses final JSON/text-equivalent output, and verifies coverage changed for successes but not for the failed cell)
- [ ] Keep failed or unprocessed cells eligible for later review. (verification: integration - `tests/test_cli_session_review.py` asserts the failed cell remains `pending` or `stale` and can be selected in a subsequent budgeted run)
- [ ] Keep fixed-finding verification scoped to successfully evaluated paths during a partial failure. (verification: unit - `tests/test_cli_session_review.py` covers a fixed finding on a successful path becoming verified and a fixed finding on a failed path remaining `fixed_pending_verification`)
- [ ] Preserve all-success and interrupt behavior. (verification: integration - existing `tests/test_cli_session_review.py` and `tests/test_review_progress.py` continue to pass without weakening cancellation assertions)
- [ ] Run focused verification for review execution behavior. (verification: integration - `uv run pytest tests/test_cli_session_review.py tests/test_review_progress.py` passes)
- [ ] Run the project quality gate after implementation. (verification: integration - `make check` passes)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal validation: `cflx openspec validate persist-partial-review-successes --strict`
Expected archive gate: `cflx openspec validate persist-partial-review-successes --archive-gate`
