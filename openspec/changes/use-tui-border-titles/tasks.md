## Implementation Tasks

- [x] Add a reusable Textual titled-pane/container for run dashboard panels in `src/review_gauntlet/run_tui.py`. Completion condition: titled dashboard panels assign their labels through `border_title` on the bordered widget/container rather than through body text. verification: unit - `uv run pytest tests/test_run_tui.py` exercises `create_run_app()` when Textual is installed and source-level expectations for border-title usage are present.

- [x] Refactor `RunApp.compose()` so titled panels wrap body `Static` widgets while preserving existing widget update IDs. Completion condition: `finalize_path`, coverage, findings, current operation, and activity body widgets can still be queried and updated by `refresh_view()` without changing run controller semantics. verification: unit - `uv run pytest tests/test_run_tui.py` covers app construction and dashboard text helpers.

- [x] Move visible panel headings out of body text helpers and into TUI border titles. Completion condition: `activity_text()`, `finalize_path_text()`, `coverage_text()`, `findings_text()`, and `current_operation_text()` no longer emit their panel heading as the first content line used by the interactive TUI. verification: unit - `tests/test_run_tui.py` asserts activity body text does not contain a standalone `Activity` heading and updates equivalent expectations for other titled sections.

- [x] Preserve explicit titled-section rendering for non-Textual compact or test summaries that still need section names. Completion condition: compact/text summary construction has an explicit helper or call path that includes `Activity`, `Finalize path`, `Session metrics`, `Findings`, and `Current operation` labels without depending on TUI body helpers to include headings. verification: unit - `tests/test_run_tui.py::test_compact_dashboard_text_keeps_required_sections` or its replacement verifies compact summaries retain required section names.

- [x] Add or update Textual CSS for border-title styling and semantic panel states. Completion condition: normal, active, blocked, failed, and finalized bordered panels keep semantic border colors and set compatible `border-title-*` styles. verification: unit - source-level or app-construction tests in `tests/test_run_tui.py` verify expected CSS tokens/classes remain present.

- [x] Run project verification. Completion condition: the repository passes formatting, linting, type checking, and tests. (verification: integration - `make check`)

## Future Work

- Manual visual inspection in a real terminal may be useful to tune spacing and colors after implementation, but it is not required to prove the functional border-title behavior.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate use-tui-border-titles --archive-gate`.

## Acceptance Notes

- Acceptance #1 archive-commitability blocker was resolved by rewriting the project verification task note into the parenthesized end-of-line verification form required by the archive gate.
