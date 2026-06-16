## Implementation Tasks

- [ ] Update `_cmd_init` in `src/review_gauntlet/cli.py` to emit explicit lifecycle metadata (`session_state`, `run_state`, `next_command`) in both JSON and default text output. (verification: integration - `uv run pytest tests/test_cli_session_review.py -k "init"`; completion condition: init JSON output contains `session_state: "active"`, `run_state: "none"`, `next_command: "review-gauntlet review"` and default text shows equivalent summary without implying a run exists)
- [ ] Keep `create_session` in `src/review_gauntlet/session_store.py` unchanged; ensure it does not call `create_run`. (verification: integration - `uv run pytest tests/test_cli_session_review.py::test_init_creates_active_session_without_run`; completion condition: after init the `runs` table has zero rows for the new session)
- [ ] Add or update tests that assert: init creates `.review-gauntlet/active-session.json`, leaves `run_count` at `0`, and review increments run count. (verification: integration - `uv run pytest tests/test_cli_session_review.py`; completion condition: new tests pass and existing init/review tests continue to pass)
- [ ] Ensure `make check` (format, lint, typecheck, test) passes after the changes. (verification: integration - `make check`; completion condition: the full project check exits successfully)

## Future Work

- None identified for this change.
