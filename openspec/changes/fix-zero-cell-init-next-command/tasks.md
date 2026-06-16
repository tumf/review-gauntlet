## Implementation Tasks

- [x] Update init next-command derivation in `src/review_gauntlet/cli.py` so `_cmd_init` emits `review-gauntlet review` only when initialized review cells exist. (verification: unit - `uv run pytest tests/test_cli_session_review.py::test_init_creates_active_session_without_run`; completion condition: positive-cell init output keeps the existing lifecycle fields and review next command)
- [x] Add or update zero-review-cell init coverage in `tests/test_init_targets.py` so package-only worktree changes assert that `next_command` is not `review-gauntlet review` and is machine-readable as absent/no-op guidance. (verification: unit - `uv run pytest tests/test_init_targets.py::test_package_only_worktree_changes_create_no_review_cells`; completion condition: the regression test fails against the current unconditional string and passes after the fix)
- [x] Verify default text output for zero-review-cell init does not instruct the developer to run `review-gauntlet review`. (verification: integration - add or update a CLI-output test in `tests/test_init_targets.py` or `tests/test_cli_session_review.py`; completion condition: text-mode output for zero cells contains no `next_command: review-gauntlet review` line)
- [x] Preserve no-selected-cell review semantics while changing only init guidance. (verification: unit - `uv run pytest tests/test_cli_session_review.py::test_review_with_no_selected_cells_does_not_create_run`; completion condition: no-selected-cell review still returns `run_id: null` and does not increment run count)
- [x] Run the project verification suite after implementation. (verification: integration - `make check`; completion condition: format-check, lint, typecheck, and tests pass)

## Future Work

- Decide separately whether zero-cell sessions should be finalizable without a review run, or whether they should be treated as intentionally non-finalizable no-op sessions.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate fix-zero-cell-init-next-command --archive-gate`
