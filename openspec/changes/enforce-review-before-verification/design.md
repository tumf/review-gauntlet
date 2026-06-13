# Design: review-before-verification ordering

## Decision

`run_verify_fixes` must be selected only after review coverage is current. Pending cells, stale cells, and target digest drift are review-evidence blockers, so they remain higher priority than fixed-finding verification.

## Rationale

Fix verification answers whether a previously detected finding is absent from relevant reviewed paths. If the review universe has stale or pending evidence, external orchestration should refresh review coverage first. Otherwise the system can appear to make progress on finding closure while the review evidence boundary is still incomplete.

## Priority Order

The status priority remains deterministic:

1. pending or stale review cells => `run_review`
2. target digest drift => `run_review`
3. untriaged or reopened findings => `triage_findings`
4. confirmed findings => `fix_confirmed_findings`
5. fixed-pending findings => `run_verify_fixes`
6. remaining finalize blockers => `resolve_finalize_blockers`
7. otherwise => `finalize`

The follow-up tests should lock the fixed-pending branch behind the first two review-work gates.

## Compatibility

This change does not alter the fixed-finding lifecycle. `run_verify_fixes` remains the correct action once coverage and target freshness blockers have been cleared.
