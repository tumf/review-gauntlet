## Implementation Tasks

- [x] Add a scoped Textual CSS/layout rule that makes `#agent_panel_container` and `#session_panel_container` stretch to the same height inside `#summary`. (verification: unit - update `tests/test_run_tui.py`; completion condition: source/CSS contract coverage confirms both summary panel containers have the height alignment rule and the rule is scoped to the summary pair)
- [x] Preserve existing non-summary panel sizing behavior. (verification: unit - update `tests/test_run_tui.py`; completion condition: the common `.panel` style is not changed to force the same height behavior onto finalize/activity/header/footer panels)
- [x] Preserve Agent/Session summary content and equal width behavior. (verification: unit - run existing `tests/test_run_tui.py`; completion condition: existing human-facing summary, panel title, and semantic style tests continue to pass)
- [x] Run focused TUI tests after implementation. (verification: integration - `uv run pytest tests/test_run_tui.py`; completion condition: all run TUI tests pass)
- [x] Run repository quality gates after implementation. (verification: integration - `make check`; completion condition: format-check, lint, typecheck, and tests all pass)

## Future Work

- Optional manual visual check: run `review-gauntlet run` in a terminal and observe that Agent and Session boxes remain equal height when an artifact row appears.

## Final Validation

Expected proposal validation: `cflx openspec validate align-tui-agent-session-panel-heights --strict --evidence warn`.
Expected archive gate: `cflx openspec validate align-tui-agent-session-panel-heights --archive-gate`.
