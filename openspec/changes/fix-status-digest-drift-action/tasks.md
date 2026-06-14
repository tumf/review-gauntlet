## Implementation Tasks

- [ ] Update status/ready freshness classification to compare current target cells with persisted session cells before treating target digest drift as review work. (verification: unit - tests in `tests/test_cli_ready.py` assert complete current-cell coverage is not classified as `run_review` solely due to whole-target digest drift)
- [ ] Preserve `run_review` priority for genuinely incomplete review coverage: pending cells, stale cells, or current target cells missing from the session ledger. (verification: unit - existing and updated `tests/test_cli_ready.py` cases for pending/stale/missing coverage continue to expect `run_review`)
- [ ] Ensure fixed-pending findings become the next action when coverage is complete even if unrelated target digest drift is present. (verification: unit - add/modify regression test asserting `next_required_action == "run_verify_fixes"` with `coverage == {"reviewed": ...}` and `finding_state_counts == {"fixed_pending_verification": ...}`)
- [ ] Update `ready` prompt priority to match corrected `status` action priority without mutating ledger state. (verification: unit - regression test snapshots ledger state before/after `ready` and asserts the prompt targets fixed-finding verification, not target digest drift review)
- [ ] Keep finalization safety explicit for dirty/freshness blockers after action-priority correction. (verification: integration - CLI status/finalize tests assert `can_finalize` remains false while unresolved blockers or unverified fixed findings remain)
- [ ] Run focused regression checks for status/ready/finalize behavior. (verification: integration - `uv run pytest tests/test_cli_ready.py tests/test_cli_finalize_checkpoint.py`)
- [ ] Run project quality gates. (verification: integration - `make check`)

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate. Expected archive gate: `cflx openspec validate fix-status-digest-drift-action --archive-gate`.
