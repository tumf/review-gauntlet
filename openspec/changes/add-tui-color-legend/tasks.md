## Implementation Tasks

- [ ] Update the run TUI legend to include priority, finding-state, and finding-progress samples in `src/review_gauntlet/run_tui.py`. Completion condition: `color_legend_tui_lines()` returns `TuiLine` fields containing `P0`, `P1`, `P2`, `P3`, `open`, `confirmed`, `dismissed`, `done`, and `find`. (verification: unit - `uv run pytest tests/test_run_tui.py::test_color_legend_matches_finding_progress_ratio` confirms the plain legend text contains the expanded samples.)

- [ ] Ensure legend colors are sourced from the same constants/maps as body content rather than duplicated literals. Completion condition: priority legend samples read from `_PRIORITY_COLORS`, finding-state samples read from `_FINDING_STATE_COLORS`, and progress samples use `_FIND_COUNT_COLOR`. (verification: unit - add or update a `tests/test_run_tui.py` assertion over `color_legend_tui_lines()` fields so the legend `TuiField.color` values match the source maps/constants.)

- [ ] Preserve existing TUI body coloring and rendering behavior. Completion condition: existing queue/rules/files priority coloring, finding-state coloring, and Rich/plain rendering helpers continue to use their current code paths with no run-controller or session-state changes. (verification: unit - run `uv run pytest tests/test_run_tui.py` to cover the TUI rendering suite.)

- [ ] Run the project quality gate. Completion condition: formatting, linting, typechecking, and tests complete successfully. (verification: integration - run `make check`.)

## Future Work

- Consider adding a separate, wider help overlay for lower-frequency color meanings such as activity labels, cell-state counts, and ID highlights if the compact legend becomes too dense.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal gate: `cflx openspec validate add-tui-color-legend --strict --evidence warn`
Expected archive gate: `cflx openspec validate add-tui-color-legend --archive-gate`
