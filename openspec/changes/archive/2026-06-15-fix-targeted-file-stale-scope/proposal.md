---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - src/review_gauntlet/review_cells.py
  - src/review_gauntlet/targets.py
  - tests/test_session_reconciliation.py
  - tests/test_cli_verify_fixes.py
  - openspec/specs/review-sessions/spec.md
---

# Fix targeted file stale scope

**Change Type**: implementation

## Problem / Context

Review Gauntlet tracks review coverage as cells keyed by file, rule, and slice. The stored `content_digest` currently represents the whole file, but reconciliation compares that digest per cell. When a developer fixes or verifies one cell in `file1`, only that selected cell receives the new file digest. Other cells for `file1` keep the old digest and can become `stale` even though the file was the intended fix target.

This violates the desired workflow semantics: a file being intentionally fixed or verified is the target of the current work and its sibling cells should not become stale merely because that same file changed. Stale coverage is only appropriate for files changed incidentally while working on another targeted file.

## Proposed Solution

Scope stale invalidation by targeted paths rather than by per-cell file digest drift alone.

When `review-gauntlet review` or `review-gauntlet verify-fixes` successfully evaluates a path, the command SHALL treat that path as an intentionally targeted path for the current step. The command SHALL refresh the current file digest for all cells with that `file_path` while preserving each sibling cell's existing state unless that sibling cell was itself selected and successfully reviewed.

Reconciliation and status coverage SHALL still surface `stale` cells for changed files that were not successfully evaluated as targeted paths. If work on `file1` also changes `file2`, then `file2` cells SHALL remain stale until reviewed, while `file1` sibling cells SHALL not be marked stale solely due to the intended `file1` modification.

## Acceptance Criteria

- Fixing or verifying a selected cell in `file1` updates freshness for all `file1` cells without marking sibling `file1` cells stale.
- Sibling cells in the targeted file keep their existing states; digest refresh alone does not promote `pending`, `stale`, or other non-selected cells to `reviewed`.
- If a different file changes incidentally during the same work, cells for that non-targeted file become or remain `stale` and continue to block finalization.
- `verify-fixes` continues to target only fixed-pending findings and does not select unrelated pending or stale cells merely to advance coverage.
- Status, ready prompt, and finalize blockers continue to report stale coverage when incidental changed files require review.

## Explicit Completion Conditions

- `src/review_gauntlet/session_store.py` exposes a durable operation that refreshes `content_digest` for all cells of a targeted `file_path` without changing their states.
- `src/review_gauntlet/cli.py` calls the file-level digest refresh after successful selected-cell evaluation in both `review` and `verify-fixes` flows.
- Reconciliation/status logic continues to classify non-targeted digest drift as `stale` and does not hide stale cells for incidental changed paths.
- Regression tests cover targeted-file sibling cells, pending sibling state preservation, and incidental changed-file stale blocking.
- Focused tests for session reconciliation and fix verification pass, and the repository quality gate passes with `make check`.

## Out of Scope

- Changing review cell identity from `file_path × rule_id × slice_id`.
- Replacing file-level digests with line-level or AST-level digests.
- Automatically marking sibling cells as reviewed without executing their review adapter work.
- Changing finding fingerprinting, triage state transitions, or adapter verdict validation.
- Implementing source-code changes as part of this proposal commit.
