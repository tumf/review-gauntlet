---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/review_adapter.py
  - src/review_gauntlet/session_store.py
  - tests/test_review_progress.py
  - tests/test_cli_session_review.py
  - openspec/specs/review-sessions/spec.md
---

# Preserve interrupted review results

**Change Type**: implementation

## Problem/Context

`review-gauntlet review` currently waits for `review_cells_concurrently(...)` to return all cell outcomes before `_cmd_review` persists findings and marks cells reviewed. If a developer interrupts the review with `Ctrl-C`, `review_cells_concurrently` re-raises `KeyboardInterrupt` before the completed results reach the persistence loop. Successful review work may remain only as per-cell artifacts and not be reflected in the session ledger.

This violates the product principle that coverage is first-class durable state and makes interrupted long reviews unnecessarily restart work that already completed.

## Proposed Solution

Persist successful cell outcomes incrementally during review execution instead of only after all futures complete. When interruption occurs, drain any already-completed futures without blocking, persist those outcomes, cancel only unfinished work, and leave unfinished cells pending for retry.

The implementation should preserve existing behavior for adapter failures: successful cells from the same run remain durable, failing or cancelled cells remain pending, and findings from successful cells are recorded against the run.

## Acceptance Criteria

- A cell whose adapter review completes successfully before interruption is marked `reviewed` in the session ledger.
- Findings from successfully completed cells are upserted and occurrence-linked to the current run before the interrupted command exits.
- Cells that are running, cancelled, not started, or failed during interruption remain `pending` and are eligible for the next review invocation.
- Already-completed futures are drained during interrupt handling without waiting for unfinished futures.
- The active session remains active after interruption.
- A subsequent `review-gauntlet review` selects only the remaining pending cells.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` persists per-cell successful outcomes before the full concurrent review batch completes.
- Interrupt handling in `review_cells_concurrently` or its replacement returns or exposes partial results for completed cells.
- `tests/test_review_progress.py` or a new focused test proves a successful cell is durable after a simulated interrupt.
- `tests/test_cli_session_review.py` or a new CLI integration test proves the next review skips already reviewed cells and retries pending cells.
- `make check` passes.

## Out of Scope

- Changing review cell states beyond the existing `pending` and `reviewed` model.
- Treating cancelled cells as reviewed.
- Recovering verdict artifacts from previous runs that were interrupted before this change ships.
- Changing resolve or finalize behavior.
