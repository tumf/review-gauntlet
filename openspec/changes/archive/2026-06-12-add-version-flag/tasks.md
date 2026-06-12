## Implementation Tasks

- [x] Wire a top-level `--version` flag in `src/review_gauntlet/cli.py` that prints `review-gauntlet {__version__}` and exits before root validation or session dispatch. (verification: unit - `uv run pytest tests/test_cli.py::test_cli_version_flag_outputs_package_version`; completion condition: the test exercises `main(["--version"])` without creating a temporary repository root or session state)
- [x] Use `src/review_gauntlet/__about__.py` as the version source rather than duplicating a literal version in CLI logic. (verification: unit - `uv run pytest tests/test_cli.py::test_cli_version_flag_outputs_package_version`; completion condition: `tests/test_cli.py` imports `__version__` and asserts CLI stdout equals `f"review-gauntlet {__version__}\n"`)
- [x] Preserve existing command parsing and validation behavior for all current subcommands. (verification: unit - run `uv run pytest tests/test_cli.py`; completion condition: existing CLI tests, including invalid flag and format rejection cases, still pass)
- [x] Run full project quality gates after implementation. (verification: integration - run `make check`; completion condition: format check, lint, typecheck, and tests all pass)

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-version-flag --archive-gate`.

## Future Work

- A structured JSON version output or richer build metadata can be proposed separately if users need machine-readable release diagnostics.
