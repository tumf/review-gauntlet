## Implementation Tasks

- [ ] Update command output configuration defaults so omitted `adapter.output` means `file-json` with the per-cell `{output_file}` path. Completion condition: `CommandOutputConfig` accepts omitted `path` for default file-json and still rejects invalid stdout-json path usage. verification: unit - `uv run pytest tests/test_command_review_adapter.py` covers default mode/path behavior.

- [ ] Update command adapter verdict collection so `file-json` reads only the resolved output file and treats stdout/stderr as audit logs, not verdict input. Completion condition: `CommandReviewAdapter.review()` succeeds from a valid output file despite non-JSON stdout and fails when the output file is missing or invalid. verification: unit - `uv run pytest tests/test_command_review_adapter.py` includes stdout-noise and missing-file cases.

- [ ] Strengthen generated prompt output instructions for file-json execution. Completion condition: generated `prompt.md` tells external commands to write the verdict JSON to the effective output file and not rely on stdout for verdict delivery when file-json is active. verification: unit - command adapter artifact tests assert the prompt contains the output-file contract and path.

- [ ] Preserve explicit `stdout-json` compatibility. Completion condition: a config with `output.mode` set to `stdout-json` still parses stdout and still rejects `output.path`. verification: unit - existing stdout-json success/failure tests remain present and pass.

- [ ] Update repository sample configuration to use the new default file-json workflow. Completion condition: `review-gauntlet.jsonc` omits explicit `output.mode: stdout-json` or explicitly documents file-json as the recommended behavior, while passing config validation. verification: integration - `uv run review-gauntlet review --config review-gauntlet.jsonc --format json --budget 1` can exercise the configured command adapter in a real session.

- [ ] Run the repository quality gate. Completion condition: format, lint, typecheck, and tests pass. verification: integration - `make check`

## Future Work

- Consider a dedicated CLI option for previewing the effective command adapter config, including resolved output mode/path, if users need easier debugging.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate default-command-file-json --archive-gate`
