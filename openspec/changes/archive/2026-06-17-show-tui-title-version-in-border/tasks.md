## Implementation Tasks

- [x] Add package version to the TUI header title helper. Completion condition: `header_title_text()` or an equivalent helper in `src/review_gauntlet/run_tui.py` includes `✻`, `Review Gauntlet`, and `v{__version__}` sourced from `review_gauntlet.__about__.__version__`. (verification: unit - update `tests/test_run_tui.py` to assert the title contains `run_tui.__version__` or the imported version value, then run `uv run pytest tests/test_run_tui.py`.)

- [x] Move the top header title into the `#session_header` border title. Completion condition: the `#session_header` `Vertical` has `border_title` set to the versioned title and the TUI body no longer yields `Static(header_title_text(), id="header_title")`. (verification: unit - add/update `tests/test_run_tui.py` source contract coverage that fails if `#session_header` lacks `border_title` wiring or still renders an `id="header_title"` body widget.)

- [x] Preserve status, metadata, and non-TUI text fallback rendering. Completion condition: `#header_status` and `#header_meta` remain rendered in the TUI body, `header_text(view)` still returns title/status/meta lines for compact text output, and metadata timeout/liveness behavior remains covered. (verification: unit - update existing `test_header_first_line_is_brand_title_and_meta_omits_timeout` or equivalent in `tests/test_run_tui.py`, then run `uv run pytest tests/test_run_tui.py`.)

- [x] Update header border-title styling without breaking semantic state styling. Completion condition: the removed/unused `#header_title` style is replaced by a `#session_header` border-title style or equivalent, and existing `.panel-active #header_status`, `.panel-blocked #header_status`, `.panel-failed #header_status`, and `.panel-finalized #header_status` styling remains present. (verification: unit - update the TUI CSS/source contract tests in `tests/test_run_tui.py`; focused tests pass with `uv run pytest tests/test_run_tui.py`.)

- [x] Verify the implementation does not affect run behavior outside header presentation. Completion condition: no source changes outside TUI header/title code and focused tests unless directly required, and CLI TUI-selection behavior remains unchanged. (verification: integration - run `uv run pytest tests/test_cli.py::test_cli_run_json_does_not_emit_tui_fallback_warning tests/test_cli.py::test_cli_run_interactive_text_with_tui_available_chooses_tui_path tests/test_run_tui.py`.)

## Future Work

- Manual visual review of `review-gauntlet run` in a real terminal may be useful to confirm the border title looks balanced with the current terminal theme, but it is not required for this focused behavior change.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate show-tui-title-version-in-border --archive-gate`.
