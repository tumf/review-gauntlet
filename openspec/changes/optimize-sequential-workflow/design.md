# Design: Efficient Sequential Workflow Priority

## Current Workflow Shape

`review-gauntlet status` reports durable session state from the ledger and current target digest comparison. `review-gauntlet ready` converts that state into a human/agent continuation prompt. These surfaces are orchestration helpers; they must not hide incomplete coverage or automatically loop commands.

The existing model already separates:

- current target cell coverage (`pending`, `stale`, `reviewed`, `superseded`)
- finding lifecycle state (`reopened`, `untriaged`, `confirmed`, `fixed_pending_verification`, terminal states)
- finalize blockers such as dirty review-universe files and target digest drift

## Priority Policy

The continuation priority should be:

1. Pending current review cells
2. Reopened findings
3. Untriaged findings
4. Confirmed findings
5. Fixed-pending verification
6. Generic stale review cells or target digest refresh
7. Commit-resolvable finalize blockers
8. Finalize

## Rationale

Pending current review cells are first because they represent current target work with no review evidence. After pending cells are exhausted, live findings should be advanced before generic stale refresh because fixing known findings often mutates target files and would make a premature stale-refresh review obsolete.

This is an efficiency policy, not a relaxation of correctness. `status.coverage` and `finalize_blockers` must continue to expose stale coverage and target digest drift. Finalization still requires both current coverage closure and live finding closure.

## Compatibility

This change preserves the constitution constraints:

- `review` still advances exactly one run.
- Unknown, stale, dirty, and unresolved states stay visible.
- Fixed findings still require later verification.
- Completion still requires coverage closure and finding closure.

The change only affects the recommended next action and ready prompt ordering.
