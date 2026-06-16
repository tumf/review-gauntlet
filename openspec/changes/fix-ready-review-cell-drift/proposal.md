---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py:_ready_prompt
  - src/review_gauntlet/cli.py:_ready_review_cells
  - tests/test_cli_ready.py
  - openspec/specs/review-sessions/spec.md
---

# Fix ready review-cell candidate drift

**Change Type**: implementation

## Problem/Context

`review-gauntlet ready` can decide that a pending or stale review-cell prompt is required from aggregate coverage counts, then fail while building the file-scoped prompt because the materialized ready review-cell list contains no cell in that state. The observed failure path was a pending review-cell ready prompt where `target_cells` was empty and `_first_file_path_from_cells()` raised `RuntimeError: ready prompt requested review cells but none were actionable`.

The canonical `Ready command SHALL emit the next skill-directed prompt` requirement already says ready prompt selection must use concrete renderable work and skip empty candidate buckets. A previous implementation fixed this for finding buckets, but review-cell buckets still use aggregate coverage counts for prompt selection.

## Proposed Solution

Make ready-prompt selection data-consistent for review cells by deriving pending and stale prompt eligibility from the materialized `_ready_review_cells()` result. Aggregate effective coverage may continue to drive status output and finalize blockers, but `ready` must not call the file-scoped review-cell prompt builder unless at least one concrete `_ReadyReviewCell` exists for the selected state.

Preserve the existing ready priority order for concrete work: pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, stale review cells, finalize.

## Acceptance Criteria

- `review-gauntlet ready --format json` does not raise a traceback when aggregate coverage counts and materialized ready review-cell candidates disagree.
- Empty pending and stale review-cell candidate buckets are skipped instead of being passed to the file-scoped prompt builder.
- If another concrete ready action exists after an empty review-cell bucket, ready returns that next valid prompt.
- If no promptable concrete work remains and finalization is still blocked, ready returns `{"prompt": null}` with the existing no-ready behavior.
- Existing file-scoped ready prompt format and ready/run prompt handoff remain unchanged for normal concrete pending and stale review-cell work.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` selects pending and stale review-cell prompts from materialized `_ReadyReviewCell` buckets rather than from aggregate coverage counts alone.
- `tests/test_cli_ready.py` includes regression coverage showing an aggregate pending or stale count cannot force `_first_file_path_from_cells()` with an empty tuple.
- Existing ready priority tests still pass and prove the priority order is unchanged when concrete work exists.
- Focused tests for ready prompt generation pass with `uv run pytest tests/test_cli_ready.py`.
- CI-equivalent validation remains available through `make check` after implementation.

## Out of Scope

- Changing review-cell state semantics or target digest computation.
- Changing the file-scoped prompt text format beyond what is needed to avoid empty target selection.
- Changing finding bucket selection, which is already covered by the prior fix.
- Changing `status`, `finalize`, or run-controller lifecycle behavior except where they directly consume the same ready prompt output.
