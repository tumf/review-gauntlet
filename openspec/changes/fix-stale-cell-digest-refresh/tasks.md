## Implementation Tasks

- [ ] Add a session-scoped reviewed-cell update in `src/review_gauntlet/session_store.py` that sets `state = reviewed` and stores the current `ReviewCell.content_digest` for the matching `session_id` and `cell_id`. (verification: unit - `tests/test_session_store.py` asserts only the target session's row changes and the stored digest is refreshed)
- [ ] Use the digest-refreshing update in `src/review_gauntlet/cli.py` only after a selected cell's adapter review succeeds. (verification: integration - `tests/test_cli_session_review.py` or `tests/test_session_reconciliation.py` runs a review with a fixture and asserts successful cells have current digests while unreviewed cells remain unchanged)
- [ ] Add a regression test for the repeated stale-selection bug: review a cell, modify its file to make it stale, re-review it successfully, then run reconciliation/review again without another file change and assert it is not stale again. (verification: integration - `tests/test_session_reconciliation.py` asserts stale count drops or remains absent for the refreshed cell and budget can advance to pending cells)
- [ ] Preserve legitimate invalidation by proving a file changed after digest refresh still marks the affected reviewed cell stale. (verification: integration - `tests/test_session_reconciliation.py` extends or complements the existing changed-target stale test)
- [ ] Preserve existing finding and fixed-verification behavior around successful review. (verification: unit - existing `tests/test_cli_session_review.py` fixed-finding tests still pass, and no task changes finding transition logic)
- [ ] Run focused verification for the affected behavior. (verification: integration - `uv run pytest tests/test_session_store.py tests/test_session_reconciliation.py tests/test_cli_session_review.py` passes)
- [ ] Run the project quality gate after implementation. (verification: integration - `make check` passes)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal validation: `cflx openspec validate fix-stale-cell-digest-refresh --strict`
Expected archive gate: `cflx openspec validate fix-stale-cell-digest-refresh --archive-gate`
