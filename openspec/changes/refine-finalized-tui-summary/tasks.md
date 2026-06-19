## Implementation Tasks

- [ ] Update finalized summary data derivation to compute changed files from `RunSnapshot.coverage_projection.queue` entries with `changed_since_review == True`, sorted and de-duplicated. (verification: unit - `uv run pytest tests/test_run_tui.py` includes a finalized snapshot with both changed and unchanged queue entries and asserts only changed paths appear)
- [ ] Update finalized finding filtering so finalized finding IDs and fixed finding count include only findings on changed files with state `fixed_pending_verification` or `fixed_verified`. (verification: unit - `uv run pytest tests/test_run_tui.py` asserts confirmed, dismissed, false-positive, accepted-risk, waived, open, and untriaged findings are excluded)
- [ ] Update finalized summary rendering labels and values from broad resolved semantics to changed-file/fixed-finding semantics while preserving coverage, run, checkpoint, and panel replacement behavior. (verification: unit - `uv run pytest tests/test_run_tui.py` asserts finalized summary text contains `Changed files`, fixed finding count, and filtered finding IDs while non-finalized sections remain unchanged)
- [ ] Add regression coverage for compact finalized output so `compact_dashboard_text()` and Rich/TUI section rendering share the same filtered finalized summary data. (verification: unit - `uv run pytest tests/test_run_tui.py` asserts compact finalized text excludes unchanged files and non-fixed findings)
- [ ] Run the project quality gate after implementation. (verification: integration - `make check`)

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate refine-finalized-tui-summary --archive-gate`
