## Implementation Tasks

- [x] Change `_cmd_verify_fixes` to use `stale_to_pending=False` in `refresh_file_digest` call (cli.py:~1057) (verification: unit - `tests/test_cli_verify_fixes.py` test that after verify-fixes with stale sibling cells, siblings remain STALE not PENDING)
- [x] Add unit test: verify-fixes does not promote stale sibling cells to PENDING (verification: unit - new test in `tests/test_cli_verify_fixes.py` creates multi-cell file with FPV finding and STALE siblings, runs verify-fixes, asserts siblings stay STALE with updated digest)
- [x] Add unit test: `_ready_prompt()` returns verify-fixes prompt when STALE siblings coexist with fixed-pending findings (verification: unit - new test in `tests/test_cli_ready.py` sets up STALE cells + FPV findings, asserts ready prompt contains "Verify fixed-pending findings")
- [x] Remove unused `current_coverage_requires_review` parameter from `_next_action()` signature and call site at `_status()` (verification: unit - `make check` passes; grep confirms parameter absent from `_next_action` signature)
- [x] Update canonical spec scenario "Ready prompt priority is deterministic" (spec.md:653) to list: pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, stale review cells, finalize (verification: integration - `cflx openspec validate fix-verify-fixes-sibling-promotion --strict` passes; `tests/test_cli_ready.py::test_ready_priority_order_is_deterministic` continues to pass with the implemented ordering)
- [x] Update canonical spec scenario "Verify fixes refreshes targeted path sibling freshness" (spec.md:507-515) to add: sibling cells are not promoted to PENDING solely because the targeted path was evaluated (verification: integration - `cflx openspec validate fix-verify-fixes-sibling-promotion --strict` passes; new verify-fixes sibling test in `tests/test_cli_verify_fixes.py` validates the no-promotion invariant)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate fix-verify-fixes-sibling-promotion --archive-gate`
