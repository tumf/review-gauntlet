## Implementation Tasks

- [x] Replace shared session-output argument wiring for `findings` with command-specific arguments in `src/review_gauntlet/cli.py`: keep `--all`, add `--format` choices `text` and `json`, default `text`, and do not register `--audience`. (verification: unit - argparse help/parse assertions in `tests/test_cli_findings.py` prove `--format {text,json}` appears and `--audience` is absent/rejected)
- [x] Preserve existing findings output behavior while renaming the text mode: default `review-gauntlet findings` emits the current text-style summary, `--format json` emits the existing JSON payload, and `--all` still includes terminal findings. (verification: unit - existing and updated `tests/test_cli_findings.py` assertions cover default output, JSON parsing, and all-flag inclusion)
- [x] Add regression coverage for invalid removed options: `review-gauntlet findings --format human` and `review-gauntlet findings --audience agent` both fail with argparse usage errors. (verification: unit - `tests/test_cli_findings.py` captures `SystemExit` with non-zero code for both invocations)
- [x] Run the repository check suite after implementation. (verification: integration - `make check` passes)

## Future Work

- Consider a separate proposal if other non-progress session commands should also remove `--audience` or rename `human` to `text`.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate remove-findings-audience-option --archive-gate`
