## Implementation Tasks

- [ ] Remove quiet heartbeat rows from the TUI Activity view model in `src/review_gauntlet/run_tui.py` so `dashboard_state(...)` builds `timeline_events` from real run events and bounded agent output rows only. (verification: unit - `uv run pytest tests/test_run_tui.py` must fail if a quiet agent still injects `agent alive no output ...` into Activity)
- [ ] Preserve quiet/liveness display in Header and Agent summary by keeping `agent_liveness_detail(...)`, `header_text(...)`, and `agent_summary_text(...)` behavior intact for quiet agents. (verification: unit - `tests/test_run_tui.py` asserts Header/Agent still show quiet duration and output recency)
- [ ] Update TUI activity tests in `tests/test_run_tui.py` to assert quiet heartbeat rows are absent across animation frames while existing event/stdout/stderr rendering and redaction remain covered. (verification: unit - `uv run pytest tests/test_run_tui.py`)
- [ ] Run the repository check suite after implementation. (verification: integration - `make check`)

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate remove-tui-quiet-heartbeat --archive-gate`
