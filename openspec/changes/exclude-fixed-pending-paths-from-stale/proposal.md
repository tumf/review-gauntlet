---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - tests/test_cli_session_review.py
  - tests/test_session_reconciliation.py
  - openspec/specs/review-sessions/spec.md
---

# Exclude Fixed-Pending Paths from Stale Coverage

**Change Type**: implementation

## Problem / Context

Fix work is performed per file path and can resolve multiple confirmed findings/rules on that same file at once. After those findings are marked `fixed_pending_verification`, that path should be handled by `review-gauntlet verify-fixes`, not by generic stale coverage refresh.

The current implementation treats any reviewed current cell whose persisted digest differs from the current file digest as `stale`, including cells on paths that have fixed-pending findings. This makes the fix target path appear as stale coverage even though the intended next responsibility is fixed-finding verification for that same path.

## Proposed Solution

Exclude paths with live `fixed_pending_verification` findings from generic stale coverage classification and reconciliation. For those paths, digest drift remains visible through fixed-pending finding state and is resolved by `verify-fixes`, which selects the relevant `(path, rule_id)` cells and refreshes their coverage digest when verification runs.

Generic stale coverage remains for reviewed current cells whose file digest changed and whose path does not have any fixed-pending findings, especially files modified incidentally while fixing another file.

## Acceptance Criteria

- `status --format json` does not report cells on paths with `fixed_pending_verification` findings as `coverage.stale` merely because the file digest changed.
- `review --budget 0 --format json` reconciliation does not persist `stale` for cells on paths with `fixed_pending_verification` findings.
- `verify-fixes` continues to select only current cells needed by fixed-pending findings and refreshes those selected cells to the current digest when they are evaluated.
- Files changed incidentally during a fix, but without fixed-pending findings on their path, still appear as stale reviewed cells.
- Finalization remains blocked while fixed-pending findings require verification, so excluding those paths from stale coverage does not hide incompleteness.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` stale reconciliation and effective status coverage share the same fixed-pending-path exclusion behavior.
- Regression tests cover fixed-pending path digest drift not becoming stale, incidental non-fixed-pending path drift still becoming stale, and verify-fixes clearing the fixed-pending path through verification.
- Focused tests covering session review/reconciliation/verification pass.
- `make check` passes.

## Out of Scope

- Changing finding fingerprinting or deduplication.
- Changing the `fixed_pending_verification` lifecycle.
- Auto-running verification or review loops.
- Hiding fixed-pending findings, unrelated stale cells, dirty review-universe blockers, or target digest drift from status/finalization output.
