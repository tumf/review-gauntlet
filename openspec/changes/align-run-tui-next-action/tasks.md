## Implementation Tasks

- [ ] Map known `RunSnapshot.next_required_action` values to the corresponding `Finalize checklist` gate in `src/review_gauntlet/run_tui.py`. Completion condition: `dashboard_state(...)` uses the mapped gate as `active_gate` for known actions without exposing the raw action string in rendered text. (verification: unit - `uv run pytest tests/test_run_tui.py` includes direct `RunSnapshot` fixtures for each mapped action.)
- [ ] Preserve data-grounded checklist row details while changing active-row selection. Completion condition: stale coverage, pending coverage, finding counts, and finalize-only blocker details remain visible in `finalize_path_text(...)` even when `next_required_action` selects a later gate. (verification: unit - `uv run pytest tests/test_run_tui.py::test_finalize_checklist_uses_next_required_action_for_active_gate_with_stale_coverage` or equivalent asserts stale coverage detail and active `Verify fixes` together.)
- [ ] Preserve fallback behavior for missing or unknown `next_required_action`. Completion condition: snapshots without a known action continue to derive the active gate from coverage, findings, blockers, finalization state, and failure state as before. (verification: unit - `uv run pytest tests/test_run_tui.py` includes an unknown-action fixture that matches existing derived-gate expectations.)
- [ ] Keep the dashboard human-facing and free of internal action names. Completion condition: rendered header, checklist, Agent, Session, and Activity text do not include `run_verify_fixes`, `run_review`, `resolve_finalize_blockers`, `finalize`, or `cleanup_git_worktree` as raw action labels. (verification: unit - `uv run pytest tests/test_run_tui.py` extends the existing internal-action-name assertions.)
- [ ] Run the repository quality gate. Completion condition: formatting, linting, strict type checking, and tests all pass. (verification: integration - `make check`.)

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate align-run-tui-next-action --archive-gate`
