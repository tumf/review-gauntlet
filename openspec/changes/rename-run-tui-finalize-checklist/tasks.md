## Implementation Tasks

- [x] Update the shared run TUI panel title source from `Next to finalize` to `Finalize checklist`. (verification: unit - `uv run pytest tests/test_run_tui.py` fails if compact dashboard text or TUI-derived titles still contain `Next to finalize`)
- [x] Update compact dashboard and TUI regression tests in `tests/test_run_tui.py` to assert the new `Finalize checklist` section title while preserving the existing panel order. (verification: unit - `uv run pytest tests/test_run_tui.py` covers `Review Gauntlet`, `Finalize checklist`, `Agent`, `Session`, and `Activity` ordering)
- [x] Preserve checklist content and behavior by keeping the six ordered rows, state labels, blocker classification, header gate text, Agent summary, Session summary, and Activity rendering unchanged. (verification: unit - existing and updated `tests/test_run_tui.py` assertions fail if row names, row states, blocker wording, or internal-action hiding regress)
- [x] Update the `review-sessions` spec delta to replace the user-visible `Next to finalize` panel name with `Finalize checklist` in the run TUI dashboard requirement and scenarios. (verification: integration - `openspec/changes/rename-run-tui-finalize-checklist/specs/review-sessions/spec.md` contains the updated dashboard requirement and scenarios; `uv run pytest tests/test_run_tui.py` verifies the corresponding user-visible title)

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate rename-run-tui-finalize-checklist --archive-gate`
