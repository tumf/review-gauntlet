## Implementation Tasks

- [x] Standardize CLI parser format choices in `src/review_gauntlet/cli.py` so `report`, `init`, `review`, `status`, `mark`, and `finalize` accept `--format {text,json}` with default `text`, and no command accepts `--format human` or `--format markdown`. (verification: unit - argparse-focused tests in `tests/test_cli.py` and session command tests fail on obsolete choices and pass on `text|json`)
- [x] Limit `--audience {human,agent}` registration to the `review` command and remove it from non-progress commands. (verification: unit - help/parse tests prove `review --help` contains `--audience`, while `init`, `status`, `mark`, `finalize`, and `findings` reject `--audience agent`)
- [x] Preserve existing output contracts while renaming the text mode: JSON payloads remain parseable, default text output remains human-readable, and `report --format text` emits the existing Markdown-style report body. (verification: integration - CLI tests execute representative commands and parse JSON or assert existing text markers)
- [x] Preserve review progress audience behavior after parser changes. (verification: unit - `tests/test_review_progress.py` confirms human progress goes to stderr for `review --format json` and `--audience agent` suppresses progress)
- [x] Update or add regression tests covering obsolete option rejection for `--format human`, `--format markdown`, and non-review `--audience`. (verification: unit - targeted pytest cases raise non-zero `SystemExit` for each obsolete option family)
- [x] Run the project quality gate after implementation. (verification: integration - `make check` passes)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal validation: `cflx openspec validate standardize-cli-output-options --strict`
Expected archive gate: `cflx openspec validate standardize-cli-output-options --archive-gate`
