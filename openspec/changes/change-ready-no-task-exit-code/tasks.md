## Implementation Tasks

- [ ] Update the `ready` command path in `src/review_gauntlet/cli.py` to compute the prompt once, emit existing output, and raise `SystemExit(1)` only when the prompt is `None` (verification: unit - `uv run pytest tests/test_cli_ready.py`).
- [ ] Add or update ready-command tests in `tests/test_cli_ready.py` so no-task JSON and text invocations assert `SystemExit.code == 1` while preserving `{"prompt": null}` and `no ready task\n` output (verification: unit - `uv run pytest tests/test_cli_ready.py`).
- [ ] Add or update ready-command tests in `tests/test_cli_ready.py` so an actionable prompt invocation completes without `SystemExit` and preserves exit code `0` semantics (verification: unit - `uv run pytest tests/test_cli_ready.py`).
- [ ] Run the repository quality gate and confirm formatting, linting, typechecking, and tests pass (verification: integration - `make check`).

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate change-ready-no-task-exit-code --archive-gate`
