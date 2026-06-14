## Implementation Tasks

- [x] Update status/ready freshness classification to compare current target cells with persisted session cells before treating target digest drift as review work. (verification: unit - tests in `tests/test_cli_ready.py` assert complete current-cell coverage is not classified as `run_review` solely due to whole-target digest drift)
- [x] Preserve `run_review` priority for genuinely incomplete review coverage: pending cells, stale cells, or current target cells missing from the session ledger. (verification: unit - existing and updated `tests/test_cli_ready.py` cases for pending/stale/missing coverage continue to expect `run_review`)
- [x] Ensure fixed-pending findings become the next action when coverage is complete even if unrelated target digest drift is present. (verification: unit - `uv run pytest tests/test_cli_ready.py::test_status_prioritizes_fixed_pending_findings_when_only_whole_digest_drifted` asserts `next_required_action == "run_verify_fixes"` with reviewed coverage and `fixed_pending_verification` findings)
- [x] Update `ready` prompt priority to match corrected `status` action priority without mutating ledger state. (verification: unit - `uv run pytest tests/test_cli_ready.py::test_ready_prompts_verify_fixes_when_only_whole_digest_drifted tests/test_cli_ready.py::test_ready_has_no_task_for_digest_drift_only_blocker_without_mutating_state` asserts the prompt targets fixed-finding verification and ledger JSON is unchanged before/after `ready`)
- [x] Keep finalization safety explicit for dirty/freshness blockers after action-priority correction. (verification: integration - `uv run pytest tests/test_cli_ready.py::test_status_keeps_digest_drift_as_finalize_blocker_when_coverage_is_complete tests/test_cli_finalize_checkpoint.py` asserts `can_finalize` remains false while unresolved blockers or unverified fixed findings remain)
- [x] Run focused regression checks for status/ready/finalize behavior. (verification: integration - `uv run pytest tests/test_cli_ready.py tests/test_cli_finalize_checkpoint.py`)
- [x] Run project quality gates. (verification: integration - `make check`)

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate. Expected archive gate: `cflx openspec validate fix-status-digest-drift-action --archive-gate`.

## Acceptance Notes

Acceptance #1 reported that archive-gate validation required repository-verifiable evidence in the verification notes for implementation tasks 3-5. Those notes now cite the concrete pytest selectors and runnable commands used as evidence.
