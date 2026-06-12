---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/session_store.py
  - src/review_gauntlet/cli.py
  - tests/test_session_store.py
  - tests/test_cli_session_review.py
  - tests/test_cli_finalize.py
---

# Repair Session Ledger and Triage Validation

**Change Type**: implementation

## Problem/Context

Confirmed findings show ledger integrity and triage metadata weaknesses: cell state updates can silently mutate zero rows, finding IDs are allocated from `count(*)`, malformed `--until` metadata can break later status/finalize commands, and zero-cell review runs can be mistaken for current review evidence.

Affected finding IDs include `RGF-0006`, `RGF-0015`, `RGF-0020`, `RGF-0022`, `RGF-0030`, `RGF-0036`, `RGF-0037`, and `RGF-0041`.

## Proposed Solution

Make ledger mutations fail explicitly when they do not affect the intended row, allocate finding IDs monotonically, validate triage date metadata before persistence, tolerate malformed persisted decision metadata conservatively, and prevent zero-cell review runs from satisfying finalization evidence.

## Acceptance Criteria

- `update_cell_state` raises an actionable error when the target session/cell row does not exist.
- New `RGF-*` IDs are based on the maximum existing numeric ID for the session, not on row count.
- Re-detected fixed-pending findings reopen deterministically and are not incorrectly verified in the same run.
- `mark --until` accepts only ISO dates and rejects malformed values before writing finding events.
- Malformed persisted terminal-decision metadata does not crash `status` or `finalize`; it is surfaced conservatively as blocking/expired decision state.
- `review` does not create or use zero-cell runs as finalization evidence.

## Explicit Completion Conditions

- Ledger and triage changes are implemented in `src/review_gauntlet/session_store.py` and `src/review_gauntlet/cli.py`.
- Tests prove failure on unknown cell updates, monotonic finding ID allocation after deleted or migrated rows, fixed-pending redetection behavior, malformed `--until` rejection, malformed persisted metadata handling, and zero-cell run behavior.
- `make check` passes.

## Out of Scope

- Database schema migrations beyond what is required for current SQLite ledger compatibility.
- Bulk triage command design or implementation.
