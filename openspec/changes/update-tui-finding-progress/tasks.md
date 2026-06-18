## Implementation Tasks

- [ ] Add resolved finding count to the coverage projection data model used by run TUI cell entries. Completion condition: `QueueEntry` or its replacement carries `resolved_finding_count` alongside `finding_count` and `actionable_finding_count`. (verification: unit - `uv run pytest tests/test_run_tui.py` exercises updated `QueueEntry` fixtures from `tests/test_run_tui.py`.)

- [ ] Compute per-cell resolved finding count from terminal finding states during projection construction. Completion condition: projection construction counts terminal finding states as resolved and leaves open/actionable findings unresolved. (verification: unit - `uv run pytest tests/test_run_tui.py` includes a mixed-state cell fixture that observes the expected resolved count.)

- [ ] Update the cells view formatter to render resolved-over-total finding progress. Completion condition: `run_tui._format_cell_entry()` or equivalent cell-entry renderer emits `findings {resolved}/{total} resolved` instead of actionable-over-total text. (verification: unit - `tests/test_run_tui.py` asserts rendered cell text includes a mixed-state example such as `findings 2/3 resolved`.)

- [ ] Preserve actionable finding behavior for prioritization and queue explanations. Completion condition: priority score, priority label, actionable queue selection, and `why` text continue to use actionable/open finding counts where they did before. (verification: unit - `uv run pytest tests/test_run_tui.py` keeps actionable-count-dependent queue and projection fixtures passing.)

- [ ] Run repository verification. Completion condition: local checks complete successfully or failures are documented with direct relevance. (verification: integration - `make check`.)

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate update-tui-finding-progress --archive-gate`
