## Implementation Tasks

- [x] Update stale reconciliation to skip fixed-pending paths in `src/review_gauntlet/cli.py` (completion: `_reconcile_cells()` does not persist `CellState.STALE` for current cells whose `file_path` is in `store.fixed_pending_paths(session_id)`, while still superseding missing cells and staling changed reviewed cells on other paths; verification: unit - add/update `tests/test_session_reconciliation.py` or `tests/test_cli_session_review.py` to fail if a fixed-pending path is persisted as stale after a digest change).

- [x] Update effective status coverage to skip fixed-pending paths when deriving stale coverage (completion: `_effective_current_target_coverage()` reports fixed-pending-path cells by their persisted state unless they are missing/superseded, instead of converting digest drift into `stale`; verification: unit - add/update a status test asserting a changed fixed-pending path has no `coverage.stale` attributable to that path and still reports `finding_state_counts.fixed_pending_verification` plus `next_required_action == "run_verify_fixes"`).

- [x] Preserve generic stale detection for incidental changed files without fixed-pending findings (completion: a reviewed file changed during a fix but with no fixed-pending finding on that path still appears as stale and remains a finalization blocker; verification: unit - add/update a regression test with two reviewed paths: one fixed-pending changed path and one unrelated changed path; only the unrelated path contributes to stale coverage).

- [x] Preserve verify-fixes selection and digest refresh behavior for fixed-pending paths (completion: `verify-fixes` continues to select the relevant current `(path, rule_id)` cells, transition fixed-pending findings to verified/reopened based on re-detection, and mark evaluated cells reviewed with the current digest; verification: integration - add/update `tests/test_cli_verify_fixes.py` to demonstrate fixed-pending path drift is resolved by `verify-fixes` rather than stale review).

- [x] Run focused and full project verification (verification: integration - focused regression tests for modified behavior and `make check` complete successfully).

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate exclude-fixed-pending-paths-from-stale --archive-gate`
