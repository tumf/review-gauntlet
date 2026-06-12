## Implementation Tasks

- [ ] Convert unexpected exceptions from `future.result()` in `review_cells_concurrently()` into `ReviewAdapterError` outcomes with structured `failure` metadata, preserving cancellation handling for `KeyboardInterrupt`. (verification: integration - `uv run pytest tests/test_cli_session_review.py tests/test_command_review_adapter.py` covers an adapter/stub raising `RuntimeError` and verifies structured failed-cell output)
- [ ] Add regression coverage for partial review runs where one cell raises an unexpected adapter exception and other cells succeed, proving successful coverage is persisted and the failed cell remains retryable. (verification: integration - `uv run pytest tests/test_cli_session_review.py` exercises partial-success semantics)
- [ ] Reject `{prompt}` in `adapter.output.path` during config validation while continuing to accept `{prompt}` in adapter `args` and `env`. (verification: unit - `uv run pytest tests/test_config.py tests/test_command_review_adapter.py` covers forbidden output-path prompt templates and still-valid argv/env prompt templates)
- [ ] Create parent directories for nested file-json output paths after `_resolve_output_path()` confirms the destination remains under the cell artifact directory and before invoking the external command. (verification: integration - `uv run pytest tests/test_command_review_adapter.py` covers `output.path` such as `out/verdict.json` written by a real subprocess)
- [ ] Normalize `target_digest()` and `file_digests()` to use a resolved repository root for both `review_universe_files()` and `relative_to()` calculations. (verification: unit - `uv run pytest tests/test_targets.py` covers `Path('.')`/relative-root digest calls and equivalent absolute-root calls)
- [ ] Add a CLI regression test proving `uv run review-gauntlet status --format json` succeeds when invoked from the repository root without an explicit root argument. (verification: integration - `uv run pytest tests/test_cli_session_review.py` or a focused CLI test exercises default-root status)
- [ ] Run full repository checks after implementation. (verification: integration - `make check`)

## Future Work

- If a future adapter output transport needs prompt-derived filenames, propose a new deterministic template phase instead of allowing `{prompt}` in `output.path`.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate fix-adapter-output-and-root-digest --archive-gate`
