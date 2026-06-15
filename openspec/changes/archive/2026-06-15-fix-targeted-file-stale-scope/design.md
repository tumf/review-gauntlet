# Design: Targeted file stale scope

## Current Behavior

Review cells are modeled per file/rule/slice, but `content_digest` is the SHA-256 digest of the entire file. A successful selected-cell review updates only the selected cell row. During later reconciliation, sibling cells for the same file can still contain the old digest, so they are classified as `stale` even when the file was the intended fix or verification target.

## Desired Freshness Model

A command step has two kinds of file changes:

- Targeted path changes: files successfully evaluated by the current `review` or `verify-fixes` step.
- Incidental path changes: files whose content changed but were not successfully evaluated by the current step.

Targeted path changes should refresh freshness for every cell on that file because the file was intentionally part of the current work. Incidental path changes should remain stale because their coverage no longer matches the current file content.

## Implementation Approach

Add a store-level helper that updates `content_digest` for every row with `(session_id, file_path)` without changing row state. Existing `mark_cell_reviewed(...)` remains responsible for marking selected successful cells as `reviewed`.

In `review` and `verify-fixes`, after a selected cell succeeds, the command should refresh the selected cell's file digest for all sibling rows for that path. This keeps sibling cells from becoming stale solely due to intended work on their own file while preserving the constitution rule that `reviewed` means executed.

## State Preservation

Digest refresh is not coverage execution. It must not promote unselected cells to `reviewed` and must not close pending work. A pending sibling remains pending after its digest refresh. A stale sibling should not be silently promoted to reviewed; only selected successful adapter work may record reviewed coverage.

## Verification Strategy

Use integration-style CLI tests with small temporary repositories and fixture adapters. The tests should prove both halves of the behavior:

- Targeted-file sibling cells no longer become stale after a successful fix/verify step.
- Non-targeted files changed incidentally still become stale and continue to block finalization.

Focused tests should exercise both `review` and `verify-fixes` because they have separate selection paths and finding-state side effects.
