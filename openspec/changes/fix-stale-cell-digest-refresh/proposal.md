---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - tests/test_session_reconciliation.py
  - tests/test_cli_session_review.py
  - openspec/specs/review-sessions/spec.md
---

# Fix Stale Cell Digest Refresh

**Change Type**: implementation

## Problem/Context

`review-gauntlet review --budget 5` can repeatedly select the same cells even after they succeed, leaving the reported `coverage.pending` count unchanged. The observed session showed the same `cli.py` and `review_adapter.py` cells being reviewed in consecutive runs while `coverage` stayed at `{'pending': 36, 'reviewed': 64, 'stale': 4}`.

Repository inspection found that `_reconcile_cells()` marks existing cells `stale` when their stored `content_digest` differs from the current digest, but successful review completion only updates the cell state to `reviewed`. The stored digest remains old, so the next review run reconciles the same cell back to `stale` before selection can move on to pending cells.

This violates the constitution's coverage principles: reviewed coverage must be recorded deterministically by code digest, and stale coverage must stay visible only until it has been re-reviewed against the current digest.

## Proposed Solution

When a current review cell succeeds, persist both of these facts atomically for that session and cell:

- the cell state is now `reviewed`
- the ledger's `content_digest` matches the current reviewed cell digest

Keep stale detection unchanged: if target content changes again after that successful review, reconciliation must still mark the affected cell stale. The change should be minimal and should not alter finding triage, finding occurrence deduplication, review selection order, run creation, or target-policy behavior.

## Acceptance Criteria

- A stale cell that succeeds during `review-gauntlet review` is not marked stale again on the next review run when its file content has not changed.
- After stale cells have been refreshed, later review runs can spend budget on remaining pending cells instead of repeatedly consuming budget on already-refreshed stale cells.
- The persisted `review_cells.content_digest` for a successfully reviewed current cell equals the digest used to build the current review cell.
- Failed, cancelled, interrupted, or unselected cells do not receive refreshed digests or reviewed coverage.
- If the file changes again after a successful refresh, reconciliation still marks the affected current cell stale.
- Existing finding creation, fixed-finding verification, and session-scoped cell identity behavior remain unchanged.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/session_store.py` exposes a session-scoped update path that can mark a cell reviewed while refreshing that cell's stored `content_digest` to the current digest.
- `src/review_gauntlet/cli.py` uses that digest-refreshing update only after adapter review succeeds for a selected current cell.
- Regression tests prove that re-reviewing a stale cell refreshes its digest and that a subsequent reconciliation does not re-stale the cell without another file change.
- Regression tests prove that a later file change still invalidates prior reviewed coverage.
- Focused tests covering session reconciliation/review behavior pass.
- `make check` passes.
- `cflx openspec validate fix-stale-cell-digest-refresh --strict` passes.

## Out of Scope

- Changing review adapter behavior, prompts, OCR rule selection, or finding normalization.
- Changing the meaning of `pending`, `reviewed`, `stale`, or `superseded` beyond refreshing the digest for successful current reviews.
- Adding automatic review loops or changing the one-run semantics of `review-gauntlet review`.
- Automatically triaging, fixing, waiving, or suppressing findings.
- Migrating old ledgers outside the normal reconciliation and review flow.
