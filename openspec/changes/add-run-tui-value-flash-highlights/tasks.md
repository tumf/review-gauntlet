## Implementation Tasks

- [ ] Add a stable value-change model for run TUI fields. (verification: unit - add focused `tests/test_run_tui.py` coverage proving quiet duration, last-output age, timeout countdown, elapsed time, and spinner-only changes do not produce changed-field markers.)
  Completion condition: `src/review_gauntlet/run_tui.py` identifies semantic field keys for header, finalize checklist, agent summary, session summary, and activity rows, with comparison values that exclude volatile elapsed/age/countdown text.

- [ ] Implement value-level flash rendering for TUI-only updates. (verification: unit - `tests/test_run_tui.py` asserts a coverage completed-count change such as `0 / 2` to `1 / 2` marks only the changed value fragment for flash rendering and does not mark the whole Session panel body.)
  Completion condition: the Textual render path can apply a temporary highlight to a changed value fragment without applying the same highlight to the entire containing panel or unrelated row text.

- [ ] Wire flash lifecycle into `RunApp.refresh_view()` without changing controller behavior. (verification: unit - `tests/test_run_tui.py` exercises refresh or helper state transitions showing flash is present immediately after a meaningful change and absent after the configured expiry.)
  Completion condition: changed semantic fields receive flash styling for a bounded refresh window, the styling is removed automatically after the window expires, and no `RunController`, session store, finding state, or finalization state APIs are changed for the visual effect.

- [ ] Cover meaningful state transitions separately from time-counter drift. (verification: unit - `tests/test_run_tui.py` includes paired fixtures for state-kind transitions and time-only changes.)
  Completion condition: liveness/status-kind changes such as `running` to `quiet` and timeout display-kind changes such as `not configured` to `in ...` are flash-eligible, while subsequent numeric time drift is not.

- [ ] Preserve existing non-TUI text and JSON behavior. (verification: integration - run `uv run pytest tests/test_run_tui.py tests/test_cli.py::test_cli_run_json_does_not_emit_tui_fallback_warning tests/test_cli.py::test_cli_run_no_tui_accepts_flag`.)
  Completion condition: existing plain-text helpers still return unmarked human-readable text, and TUI-specific markup or widget styling does not appear in JSON or `--no-tui` output.

## Future Work

Optional manual visual review in a real terminal to tune flash color contrast and duration after automated tests pass.

## Final Validation

Expected archive gate: `cflx openspec validate add-run-tui-value-flash-highlights --archive-gate`.
