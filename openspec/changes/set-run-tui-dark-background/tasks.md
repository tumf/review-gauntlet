## Implementation Tasks

- [ ] Update the run TUI CSS to define a dark dashboard palette for `Screen` and the primary dashboard containers in `src/review_gauntlet/run_tui.py`. Completion condition: `RunApp.CSS` includes explicit dark background styling for `Screen`, `#body`, `#session_header`, `.panel`, and `#controls`, or an equivalent scoped dark-surface rule covering those containers. (verification: unit - inspect `tests/test_run_tui.py` source/CSS contract coverage and run `uv run pytest tests/test_run_tui.py`.)

- [ ] Preserve existing TUI brand and semantic status styling while adding the dark backgrounds. Completion condition: `$brand: #d97757;`, `#header_title { color: $brand;`, `.panel-active #header_status { color: $success; }`, and `.panel-failed #header_status { color: $error; }` remain covered by existing tests. (verification: unit - `uv run pytest tests/test_run_tui.py` must keep the existing header/brand/status CSS tests passing.)

- [ ] Add focused regression coverage for the explicit dark TUI background contract in `tests/test_run_tui.py`. Completion condition: a test fails if the dark background token or `Screen` background rule is removed, and checks at least one primary container dark-surface rule. (verification: unit - `uv run pytest tests/test_run_tui.py`.)

- [ ] Verify the implementation does not affect non-TUI run output or controller behavior. Completion condition: no changes are made outside TUI styling/tests unless required by tests, and existing CLI run selection tests continue to pass. (verification: unit - `uv run pytest tests/test_cli.py::test_cli_run_json_does_not_emit_tui_fallback_warning tests/test_cli.py::test_cli_run_interactive_text_with_tui_available_chooses_tui_path tests/test_run_tui.py`.)

## Future Work

- Manual visual review of `review-gauntlet run` in a real terminal may be useful to fine-tune color contrast, but it is not required for this minimal dark-background change.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate set-run-tui-dark-background --archive-gate`.
