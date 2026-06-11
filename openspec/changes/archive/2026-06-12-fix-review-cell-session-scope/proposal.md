---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/session_store.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/review_cells.py
  - tests/test_session_store.py
  - tests/test_init_targets.py
  - openspec/specs/review-sessions/spec.md
---

# Fix review cell session scoping

**Change Type**: implementation

## Problem / Context

`review-gauntlet init --all` can fail after a prior `review-gauntlet init` has created durable state in the same repository. Review cell IDs are deterministic for a file, rule, and slice, but the SQLite schema currently stores `review_cells.cell_id` as a table-wide primary key. A later session that contains the same logical review cell attempts to insert the same `cell_id` and fails with `sqlite3.IntegrityError: UNIQUE constraint failed: review_cells.cell_id`.

The same table-wide identity assumption also makes coverage updates unsafe: `SessionStore.update_cell_state()` updates rows by `cell_id` alone, so a future ledger containing multiple sessions with the same deterministic cell ID could update the wrong session's coverage.

The user explicitly decided that migration support for existing `.review-gauntlet/ledger.sqlite` files is out of scope.

## Proposed Solution

Scope review cell identity to the session by using `(session_id, cell_id)` as the durable ledger identity. Keep deterministic `cell_id` values unchanged for prompts, adapter fixtures, and per-session coverage display, but ensure storage and state transitions always qualify cell updates with the active session.

Do not add schema migration logic for existing ledgers. Existing local ledgers created with the old schema may be discarded and recreated by users when needed.

## Acceptance Criteria

- Running `review-gauntlet init` followed by `review-gauntlet init --all` in the same repository creates two sessions instead of raising a unique constraint failure.
- Review cells remain deterministic within each session and preserve the existing `RGC-...` cell ID format.
- Cell state updates affect only the active/intended session, even when another session contains the same deterministic `cell_id`.
- Existing review and status behavior continues to report coverage for the active session only.
- No migration support is implemented for pre-existing old-schema ledger databases.

## Explicit Completion Conditions

- `src/review_gauntlet/session_store.py` defines `review_cells` with a composite primary key over `session_id` and `cell_id`.
- `SessionStore.update_cell_state` requires a `session_id` and its SQL update qualifies both `session_id` and `cell_id`.
- All runtime callers in `src/review_gauntlet/cli.py` pass the intended active session ID when marking cells reviewed, stale, or superseded.
- Regression tests prove repeated session initialization with overlapping deterministic cells succeeds.
- Regression tests prove updating a cell in one session does not mutate the same `cell_id` in another session.
- Verification commands pass: `make check`.

## Out of Scope

- Migrating existing old-schema `.review-gauntlet/ledger.sqlite` files.
- Changing deterministic cell ID generation or the `RGC-...` prompt-visible identifier format.
- Adding a command to clear or repair old review-gauntlet state.
