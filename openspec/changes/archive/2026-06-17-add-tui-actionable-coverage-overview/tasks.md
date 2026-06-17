## Implementation Tasks

- [x] Add typed coverage projection models for queue entries, rule summaries, file summaries, finding summaries, and active/detail view state; completion condition: `src/review_gauntlet/run_tui.py` or a helper module exposes typed structures or dataclasses used by the TUI instead of string-parsing coverage/finding display text (verification: unit - `uv run pytest tests/test_run_tui.py` covers synthetic projection model construction and model fields).

- [x] Derive actionable overview projections from current review cells and live findings; completion condition: projection code uses the same stale/current-cell rules as status/readiness and associates actionable findings with file/rule cells where possible (verification: unit - `uv run pytest tests/test_run_tui.py` or a new focused test module covers pending, stale, reviewed, superseded, actionable finding, and fixed-pending verification inputs).

- [x] Implement deterministic priority scoring and P0/P1/P2/P3 queue labels; completion condition: queue ordering is stable for equal scores and favors actionable findings, stale cells, pending cells, high-risk rules, changed files, and finding counts according to documented rules (verification: unit - `uv run pytest tests/test_run_tui.py` asserts queue sort order and priority labels for representative mixed cells).

- [x] Render the run TUI overview as aggregate status plus prioritized queue, rule coverage, file hotlist, findings, and activity rather than a full coverage matrix; completion condition: overview render functions and Textual layout in `src/review_gauntlet/run_tui.py` show actionable projections and do not enumerate every file × rule cell as a matrix (verification: unit - `uv run pytest tests/test_run_tui.py` asserts overview text contains queue/rule/file projection content and does not contain matrix-style full cell grids).

- [x] Add focused files, rules, cells, findings, and agent views with keyboard navigation; completion condition: keybindings in `src/review_gauntlet/run_tui.py` expose `1` overview, `2` files, `3` rules, `4` cells, `5` findings, and agent detail access without breaking `q`, `ctrl+c`, `r`, or help behavior (verification: unit - `uv run pytest tests/test_run_tui.py` verifies view switching and existing bindings retain their current actions).

- [x] Add filtering/search affordances for actionable cell projections; completion condition: filters for stale, pending, blockers, rule prefix, file prefix, and open findings can be applied to queue/cells views (verification: unit - `uv run pytest tests/test_run_tui.py` or a new focused test module asserts each filter returns only matching cells and preserves deterministic ordering).

- [x] Implement responsive overview rendering for wide, medium, and narrow terminal widths; completion condition: rendering logic in `src/review_gauntlet/run_tui.py` prioritizes status, coverage summary, finalize blockers, next review queue, and activity under narrow widths, while wider layouts include rule coverage and file hotlist side-by-side or stacked (verification: unit - `uv run pytest tests/test_run_tui.py` simulates representative widths and asserts which sections are present or omitted).

- [x] Preserve existing finalization, coverage, finding, JSON/text, and run-controller behavior; completion condition: no product behavior changes occur outside the interactive TUI display/projection path except internal typed data needed to feed it (verification: integration - `make check` passes, including existing CLI and run-controller tests).

## Future Work

- Optional viewported matrix view can be added later if users need symbolic matrix navigation after queue/files/rules/cells views are available.
- Mouse support and persisted user layout preferences are intentionally deferred.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-tui-actionable-coverage-overview --archive-gate`
