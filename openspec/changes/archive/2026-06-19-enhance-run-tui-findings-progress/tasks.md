## Implementation Tasks

- [x] Add transient active-step metadata to run snapshots without changing durable session state. Completion condition: `src/review_gauntlet/run_controller.py` exposes `active_step_action` and `active_target_finding_ids` (or equivalent names) on `RunSnapshot`, sets them from the ready task and parsed `ProgressTarget` while a command is running, and clears them after command completion. (verification: unit - `tests/test_run_controller.py` or targeted run-controller tests assert running snapshots include targeted finding IDs and post-step snapshots clear them.)

- [x] Render Findings panel titles from resolved/total state and review activity state. Completion condition: `src/review_gauntlet/run_tui.py` renders `Findings {resolved}/{total}` in overview/findings views outside active review execution, and renders `Finding`, `Finding.`, `Finding..`, `Finding...` while the active running action is `run_review`. (verification: unit - `tests/test_run_tui.py` asserts resolved/total title output and all four review animation frames.)

- [x] Add resolve-target row indicators to Findings rows. Completion condition: `findings_tui_lines(...)` or equivalent rendering code adds an aligned indicator column and shows the current spinner frame only for findings in `active_target_finding_ids` while the active running action is `resolve_findings`. (verification: unit - `tests/test_run_tui.py` asserts the targeted finding line contains a spinner, non-targeted rows are aligned with blank indicator space, and indicators disappear when no active target IDs are present.)

- [x] Preserve existing TUI modes and finalized behavior. Completion condition: finalized snapshots continue replacing operational sections with the finalized summary, `agent` view continues showing agent summary in the bottom-left panel, and `files`/`rules`/`cells` views preserve empty bottom-left titles. (verification: unit - existing `tests/test_run_tui.py` finalized/view tests pass, with updates only where titles intentionally changed.)

- [x] Run repository verification. Completion condition: the full project check command completes successfully. (verification: integration - `make check`)

## Future Work

None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate enhance-run-tui-findings-progress --archive-gate`
