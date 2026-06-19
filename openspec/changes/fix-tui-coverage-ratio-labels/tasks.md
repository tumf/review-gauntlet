## Implementation Tasks

- [ ] Replace the mistaken legend display path with panel-local compact labels in `src/review_gauntlet/run_tui.py`. Completion condition: the active Textual compose/refresh path no longer creates or updates the added global/footer color legend, while the existing controls footer remains available. (verification: unit - `tests/test_run_tui.py` asserts the active render path does not require or update `color_legend_tui_lines()` output.)

- [ ] Add compact column headers to `Rule coverage` rows. Completion condition: `rules_tui_lines()` renders a header using the shared column vocabulary `prio`, `target`, `cells`, and `fix`, and rule rows keep compact ratio values under those columns. (verification: unit - `tests/test_run_tui.py` renders `rules_tui_lines()` and asserts the header plus a representative `cells` reviewed/total and `fix` resolved/total row.)

- [ ] Add compact column headers to `File hotlist` rows. Completion condition: `files_tui_lines()` renders the same column vocabulary as `rules_tui_lines()`, with file paths as the `target` values. (verification: unit - `tests/test_run_tui.py` renders `files_tui_lines()` and asserts the header plus a representative file row.)

- [ ] Keep compact/plain dashboard output aligned with the TUI semantics. Completion condition: `rule_coverage_text()` / `file_hotlist_text()` and their format helpers expose the same `cells` and `fix` meanings without long repeated labels. (verification: unit - `tests/test_run_tui.py` covers compact/plain render output for both panels.)

- [ ] Update or remove color-legend-specific tests that encode the mistaken behavior. Completion condition: tests no longer require `P0 P1 P2 P3 open confirmed dismissed done find` to appear in a footer/global legend, and instead verify compact ratio labeling inside the relevant panels. (verification: unit - `uv run pytest tests/test_run_tui.py`.)

- [ ] Run the project quality gate. Completion condition: formatting, linting, typechecking, and tests complete successfully. (verification: integration - `make check`.)

## Future Work

- If users later need more explanation than the compact headers provide, consider a separate opt-in help overlay rather than a persistent footer/global legend.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal gate: `cflx openspec validate fix-tui-coverage-ratio-labels --strict --evidence warn`
Expected archive gate: `cflx openspec validate fix-tui-coverage-ratio-labels --archive-gate`
