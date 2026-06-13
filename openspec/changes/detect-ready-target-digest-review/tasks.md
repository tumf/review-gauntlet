## Implementation Tasks

- [ ] Classify target digest drift as review work in status action selection. Completion condition: when `_finalize_reasons` includes `target digest has changed since the last review run` and no higher-priority open finding/cell state applies, `status` returns `next_required_action: run_review`. (verification: unit - add or update a focused test in `tests/test_cli_ready.py` or `tests/test_cli_session_review.py` that runs `uv run pytest <test-path>::<test-name>` and asserts the JSON status value)

- [ ] Return a review-oriented ready prompt for target digest drift before stale cell persistence. Completion condition: `ready --format json` returns a string prompt and exits `0` when ledger cell counts appear fully reviewed but finalize blockers include target digest drift. (verification: unit - add or update a focused test in `tests/test_cli_ready.py` that invokes `main(["ready", root, "--format", "json"])` before any `review` reconciliation)

- [ ] Preserve read-only behavior for `status` and `ready`. Completion condition: the new status/ready tests assert review cell rows, finding rows, run rows, and checkpoint files are unchanged by the commands in the drift-only scenario. (verification: unit - sqlite ledger/checkpoint assertions in `tests/test_cli_ready.py` or an adjacent focused CLI test)

- [ ] Preserve existing dirty-git and true no-task behavior. Completion condition: existing ready tests for dirty finalize blockers and non-commit/non-drift blockers continue to pass without broadening dirty blocker handling. (verification: unit - `uv run pytest tests/test_cli_ready.py`)

- [ ] Run project checks. Completion condition: repository checks complete successfully without unrelated changes. (verification: integration - `make check`)

## Future Work

None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate detect-ready-target-digest-review --archive-gate`
