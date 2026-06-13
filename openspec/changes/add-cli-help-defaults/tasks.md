## Implementation Tasks

- [ ] Add default-aware help text to CLI parser arguments in `src/review_gauntlet/cli.py`, without changing parser defaults or accepted arguments (verification: unit - `uv run pytest tests/test_cli.py -k "help or defaults or completion"` confirms help defaults appear and existing parser behavior tests still pass).
- [ ] Add representative CLI help tests in `tests/test_cli.py` covering optional root defaults, `--format`, numeric defaults, boolean defaults, repeatable filter defaults, metadata string defaults, and audience defaults (verification: unit - `uv run pytest tests/test_cli.py -k help` exercises the new assertions).
- [ ] Confirm shell completion option discovery still derives from parser-visible option strings and is not broken by the help-only changes (verification: unit - `uv run pytest tests/test_cli.py::test_cli_completion_outputs_script_for_supported_shells` continues to pass).
- [ ] Run the project check suite to verify formatting, linting, typing, and tests (verification: integration - `make check`).

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-cli-help-defaults --archive-gate`
