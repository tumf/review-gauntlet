# Design: Excluding Fixed-Pending Paths from Generic Stale Coverage

## Current Behavior

`review-gauntlet` stores review-cell coverage with a file digest. Reconciliation and effective status coverage currently classify any current cell with a digest mismatch as `stale`.

This is correct for reviewed files that changed outside the active finding-fix path, but it is too broad for fix workflows. A confirmed finding can be fixed alongside other findings on the same path, then marked `fixed_pending_verification`. At that point, the path is not unknown generic stale work; it is known verification work.

## Intended Model

There are two separate freshness responsibilities:

1. **Fixed-pending path freshness**: handled by finding state and `verify-fixes`.
2. **Incidental changed reviewed-file freshness**: handled by generic stale review cells.

A path with at least one live `fixed_pending_verification` finding belongs to the first responsibility. Its digest drift should not also create generic stale work for the same path.

## Implementation Approach

Use `SessionStore.fixed_pending_paths(session_id)` as the deterministic exclusion set for stale classification in both places that compute stale state:

- `_reconcile_cells()` when mutating persisted review-cell state before review/verification commands.
- `_effective_current_target_coverage()` when producing read-only status/ready/finalize coverage summaries.

The exclusion applies only to converting digest mismatch into `stale`. It does not suppress:

- missing current cells becoming pending,
- persisted cells no longer in the target becoming superseded,
- fixed-pending finding counts,
- fixed-pending finalization blockers,
- unrelated stale cells on other paths.

## Verification Strategy

Tests should prove the split explicitly:

- fixed-pending path digest drift remains non-stale and visible through finding state,
- incidental changed reviewed files still become stale,
- verify-fixes remains the path that evaluates fixed-pending findings and refreshes selected cell digests.

## Compatibility Notes

This changes prior tests that expected fixed-pending path digest drift to contribute to `coverage.stale`. Those tests should be updated because the intended workflow now treats that case as verification work, not stale review work.
