# Design: status coverage priority enforcement

## Decision

`status.next_required_action` must model the next safest orchestration step, not merely the most concrete unresolved finding state. Incomplete or stale review coverage means the review universe is not fully current, so review work takes precedence over fixing confirmed findings.

## Rationale

The constitution defines coverage as a product and requires unknown/stale states to remain visible. A confirmed finding is important, but fixing it before refreshing incomplete coverage can cause orchestrators to focus on known issues while leaving unreviewed or stale code outside the current evidence boundary.

## Implementation Shape

The implementation should keep `_next_action` as a deterministic priority function:

1. pending or stale review cells => `run_review`
2. target digest drift => `run_review`
3. untriaged or reopened findings => `triage_findings`
4. confirmed findings => `fix_confirmed_findings`
5. fixed-pending findings => `run_verify_fixes`
6. remaining finalize blockers => `resolve_finalize_blockers`
7. otherwise => `finalize`

Regression tests should exercise the exact mixed states that are easy to break during refactors: incomplete coverage with confirmed findings.

## Compatibility

This change preserves existing behavior for sessions where coverage is complete. Confirmed findings still become the next required action after pending/stale coverage and target digest drift have been resolved.
