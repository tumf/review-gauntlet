## Implementation Tasks

- [ ] Add a TUI helper for actionable finding summary counts. (verification: unit - add or update `tests/test_run_tui.py`; completion condition: a snapshot with `findings={"untriaged": 2, "confirmed": 1, "fixed_pending_verification": 1}` and no `open` key produces derived open count `4` with triage/fix/verify components)
- [ ] Update Session panel findings rendering to use the derived actionable count and breakdown. (verification: unit - update `tests/test_run_tui.py::test_agent_session_summary_and_activity_rows_are_human_facing_and_sanitized` or add a focused test; completion condition: `session_summary_text()` renders non-zero `open` from actionable states and no longer relies on an `open` input key)
- [ ] Update detailed findings text to use the same derived open count. (verification: unit - update `tests/test_run_tui.py` coverage around `findings_text()`; completion condition: `findings_text()` shows derived `open` consistently with Session summary while preserving actual per-state counts)
- [ ] Preserve zero-actionable behavior. (verification: unit - add or update `tests/test_run_tui.py`; completion condition: snapshots with only terminal or absent finding counts render `open 0` without triage/fix/verify work counts)
- [ ] Run focused TUI tests after implementation. (verification: integration - `uv run pytest tests/test_run_tui.py`; completion condition: all run TUI tests pass)
- [ ] Run repository quality gates after implementation. (verification: integration - `make check`; completion condition: format-check, lint, typecheck, and tests all pass)

## Future Work

- None.

## Final Validation

Expected proposal validation: `cflx openspec validate fix-tui-findings-summary --strict --evidence warn`.
Expected archive gate: `cflx openspec validate fix-tui-findings-summary --archive-gate`.
