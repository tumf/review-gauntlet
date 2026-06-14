# Design: Effective Status Coverage

## Current Behavior

`_status()` currently queries persisted review cell counts directly from `review_cells` and returns those counts as `coverage`. It separately computes current coverage freshness through `_current_review_coverage_requires_review()`, which means the public coverage summary can lag behind the current target while `next_required_action` and finalize blockers partially reflect current state.

`_reconcile_cells()` mutates persisted review cell rows, but it is only invoked by review execution paths. Calling it from `status` would make status no longer read-only.

## Proposed Approach

Introduce a read-only effective coverage computation for status:

1. Load the active session metadata and target.
2. Build current target cells with the same path, digest, and plan logic used by review execution.
3. Load persisted review cells for the session.
4. Derive effective states without writing anything:
   - missing current cell in persisted rows => `pending`
   - persisted reviewed cell with matching digest => `reviewed`
   - persisted cell with digest mismatch => `stale`
   - persisted current cell already pending/stale/failed/reopened-equivalent state => preserve the actionable non-reviewed state
   - persisted cells absent from the current target => `superseded`
5. Return effective counts as `coverage`.

If consumers still need raw persisted counts later, add a separate `persisted_coverage` field only if necessary. The default proposal intentionally keeps the public `coverage` field as the user-facing effective status because that is what agents act on.

## Read-Only Guarantee

The effective coverage helper must not call `store.add_cells()`, `store.update_cell_state()`, `store.mark_cell_reviewed()`, `store.create_run()`, or any checkpoint writer. Tests should compare ledger/checkpoint state before and after `status` for drift scenarios.

## Interaction with Existing Priorities

The existing priority order should remain:

1. pending review cells
2. target digest drift requiring current target review
3. untriaged or reopened findings
4. confirmed findings
5. fixed-pending verification
6. stale review cells
7. other finalize blockers
8. finalize

The difference is that pending/stale decisions should be based on effective current-target coverage, so public `coverage` and `next_required_action` agree.

## Compatibility

This is a behavior correction to the JSON status contract. Existing fields remain present. The semantic meaning of `coverage` becomes the effective current-target status rather than a raw persisted ledger count. This matches the command name and expected agent workflow better than exposing stale raw storage as the primary status.
