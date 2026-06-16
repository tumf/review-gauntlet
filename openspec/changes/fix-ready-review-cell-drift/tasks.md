## Implementation Tasks

- [ ] Make review-cell ready prompt selection use concrete pending and stale `_ReadyReviewCell` buckets from `_ready_review_cells()` before calling `_review_cell_ready_prompt()`. (verification: unit - `uv run pytest tests/test_cli_ready.py::test_ready_skips_empty_review_cell_bucket_without_traceback`; completion condition: an empty concrete pending/stale bucket cannot call `_first_file_path_from_cells()` even when aggregate coverage reports that state)
- [ ] Preserve deterministic ready priority when concrete review cells and actionable findings coexist. (verification: unit - `uv run pytest tests/test_cli_ready.py::test_ready_priority_order_is_deterministic`; completion condition: prompts still select pending review cells before findings and stale review cells after fixed-pending findings when concrete candidates exist)
- [ ] Add regression coverage for falling through from an empty review-cell bucket to the next concrete actionable finding. (verification: unit - add or update a test in `tests/test_cli_ready.py`; completion condition: a monkeypatched aggregate pending or stale count with no matching materialized review cell returns the next concrete finding prompt instead of tracebacking)
- [ ] Add regression coverage for the no-ready fallback when review-cell aggregate counts disagree with materialized candidates and no other promptable work exists. (verification: unit - add or update a test in `tests/test_cli_ready.py`; completion condition: `ready --format json` exits with the existing no-ready behavior and outputs `{"prompt": null}`)
- [ ] Run focused ready tests after implementation. (verification: integration - `uv run pytest tests/test_cli_ready.py`; completion condition: all ready prompt tests pass without changing JSON output shape)
- [ ] Run repository quality gates after implementation. (verification: integration - `make check`; completion condition: format-check, lint, typecheck, and tests all pass)

## Future Work

- None.

## Final Validation

Expected proposal validation: `cflx openspec validate fix-ready-review-cell-drift --strict --evidence warn`.
Expected archive gate: `cflx openspec validate fix-ready-review-cell-drift --archive-gate`.
