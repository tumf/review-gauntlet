## Implementation Tasks

- [x] Preserve finalized run snapshot data in `src/review_gauntlet/run_controller.py` before active-session disappearance can force empty coverage/finding fallback. (verification: unit - `tests/test_run_controller.py` constructs a finalizing run path and asserts `controller.snapshot()` after finalization still reports finalized status with the pre-finalization coverage counts and non-zero `cell_terminal_count`)
- [x] Add a finalized summary data model or equivalent derived view state in `src/review_gauntlet/run_tui.py` containing final coverage, reviewed/total cells, resolved finding totals, resolved file paths, rule IDs, finding IDs, elapsed time, step count, and checkpoint commit metadata. (verification: unit - `tests/test_run_tui.py` builds a finalized `RunSnapshot`/result fixture and asserts the summary fields are derived deterministically, including explicit none/zero wording when optional categories are empty)
- [x] Render a finalized TUI summary screen that replaces operational guidance with completion-oriented statistics and achievements. (verification: unit - `tests/test_run_tui.py` asserts rendered finalized text includes final percent, terminal/total cells, elapsed time, step count, commit short SHA or commit-unavailable reason, resolved files, rules, and finding IDs)
- [x] Hide finalized-time queue, rule coverage, file hotlist, findings projection, and activity panels while preserving normal non-finalized panels. (verification: unit - `tests/test_run_tui.py` asserts `tui_render_sections()` or the render-state helper returns empty/hidden operational sections for finalized views and unchanged queue/rules/files/findings/activity sections for a running/idle view)
- [x] Keep finalized progress display stable across the final worker refresh. (verification: integration - `tests/test_run_tui.py` or `tests/test_run_controller.py` simulates `_completed_result` followed by `refresh_view()` or equivalent snapshot rebuild and asserts `header_status_tui_lines()` or rendered finalized header text does not regress to `0%` when final coverage was non-zero)
- [x] Preserve non-TUI output compatibility and existing failure/blocked TUI states. (verification: integration - existing `tests/test_cli.py`, `tests/test_run_controller.py`, and `tests/test_run_tui.py` continue to pass, and focused assertions prove structured run result keys such as `completed`, `reason`, `steps`, `step_count`, `session_id`, and `checkpoint_commit` are not removed)
- [x] Run the project quality gate after implementation. (verification: integration - `make check` passes)

## Future Work

- Visual polish or screenshot-based TUI approval can be done manually after implementation if desired, but the functional completion summary must be covered by repository tests first.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal validation: `cflx openspec validate show-finalized-run-summary --strict`
Expected evidence validation: `cflx openspec validate show-finalized-run-summary --strict --evidence warn`
Expected archive gate: `cflx openspec validate show-finalized-run-summary --archive-gate`
