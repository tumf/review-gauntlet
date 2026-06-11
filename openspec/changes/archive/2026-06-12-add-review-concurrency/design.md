# Design: Review Concurrency Control

## Current Flow

`review-gauntlet review` currently performs these steps in `src/review_gauntlet/cli.py`:

1. Resolve the active session and create one run record.
2. Reconcile review cells against the current target universe.
3. Iterate session cells sequentially until `--budget` is reached.
4. Invoke `adapter.review(selected)` for each selected cell.
5. Normalize adapter comments into findings, update the cell to `reviewed`, verify fixed findings, and emit status.

This flow is deterministic but serializes all adapter work.

## Proposed Flow

The new flow should separate deterministic selection, concurrent execution, and deterministic ledger application:

1. Validate `--concurrency >= 1`.
2. Resolve the active session and create one run record as today.
3. Reconcile cells as today.
4. Build the current cell map once from the current inventory/plan/digests.
5. Select eligible cells in existing ledger row order up to `--budget`.
6. Execute adapter review calls for selected cells with a concurrency bound.
7. Apply results in selected-cell order on the main path:
   - normalize comments
   - upsert findings and occurrences
   - update successful cell coverage
   - collect deterministic `finding_ids`
8. Verify fixed findings using the evaluated paths and fingerprints from committed successful reviews.
9. Emit the same status shape as today.

## Concurrency Boundary

The concurrency boundary should wrap only adapter execution. `SessionStore` writes should remain outside worker tasks to avoid introducing SQLite write concurrency and to preserve output ordering.

`CommandReviewAdapter.review()` already writes artifacts under a per-cell directory, so concurrently running adapter subprocesses should not share prompt, verdict, stdout, stderr, or command metadata paths.

## Failure Handling

A failed adapter result should preserve the existing contract: the failed cell is reported, the command exits non-zero, and the failed cell is not marked reviewed. If some earlier selected cells were successfully committed before the failure is surfaced, their ledger updates may remain. Results should be interpreted in selected-cell order so `failed_cell_id` and `finding_ids` are stable across runs.

The implementation may attempt to cancel pending futures after a failure, but cancellation mechanics are not part of the user-visible contract because already-started subprocesses may not be interruptible without additional process management.

## Trade-offs

- Thread-based concurrency is sufficient because adapter execution is dominated by subprocess and external LLM I/O.
- Main-path ledger writes avoid having to make `SessionStore` thread-safe.
- Defaulting to `8` matches Alibaba OCR documentation, but the option remains explicit for projects that need lower adapter or API pressure.
