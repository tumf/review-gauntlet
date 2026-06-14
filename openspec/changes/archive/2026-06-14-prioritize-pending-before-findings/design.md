# Design: Pending-First Continuation Priority

## Rationale

Review sessions have two different kinds of incomplete coverage:

- `pending`: cells that have not been reviewed in the current session coverage pass.
- `stale`: cells that were reviewed before but no longer match current content or target truth.

The efficient orchestration goal is not simply "all coverage before findings." Instead, it is:

1. Finish the first pass over never-reviewed pending cells.
2. Triage and fix findings from that pass.
3. Review stale or verification-related work after fixes have had a chance to create stale cells.

This avoids refreshing stale review coverage before the fix phase creates more stale work.

## Target Ordering

The CLI should expose this order through both `status.next_required_action` and `ready`:

1. pending review cells
2. target digest drift
3. reopened / untriaged findings
4. confirmed findings
5. fixed-pending verification
6. stale review cells
7. finalize blockers
8. finalize

## Integration Points

- `_next_action()` in `src/review_gauntlet/cli.py` decides the machine-readable next action.
- `_ready_prompt()` in `src/review_gauntlet/cli.py` decides the orchestration prompt.
- `_finalize_reasons()` remains conservative and should continue listing all blockers independently of the selected next action.
- `_select_review_cells()` may continue selecting stale cells when `run_review` is invoked; this change only affects which continuation action is recommended first.

## Verification Strategy

Unit tests should cover priority edges rather than adapter behavior:

- pending plus untriaged findings selects pending review.
- stale plus untriaged findings selects triage.
- stale plus confirmed findings selects fixing.
- stale plus fixed-pending findings selects verification.
- stale-only selects stale review.

These cases prevent both regressions: prematurely triaging before the first pending pass completes, and prematurely refreshing stale coverage before fix-driven stale work is produced.
