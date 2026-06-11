## Implementation Tasks

- [ ] Simplify command adapter config by removing `InputMode`, `CommandInputConfig`, and the `input` field from `CommandAdapterConfig`; add `{prompt}` to supported template variables, remove `{prompt_file}`, and default `timeout_seconds` to 600 seconds. (verification: unit - update `tests/test_config.py` to reject legacy `input`, reject `{prompt_file}`, accept `{prompt}` in args/env, assert `timeout_seconds` defaults to 600, and keep non-positive timeout rejection)
- [ ] Update `CommandReviewAdapter` to expand `{prompt}` into argv/env templates, stop using stdin prompt transport, stop exposing prompt-file transport variables, and keep prompt artifacts only as evidence. (verification: integration - update `tests/test_command_review_adapter.py` with an opencode-like fake command that receives prompt text as an argv element and writes a file-json verdict)
- [ ] Change cwd default behavior so omitted `cwd` passes `cwd=None` to subprocess and inherits the caller's current working directory; keep explicit configured cwd template expansion. (verification: integration - add `tests/test_command_review_adapter.py` cases where a fake command reports inherited cwd and configured cwd separately)
- [ ] Preserve env inheritance without fixed automatic variables, while keeping explicit configured env overrides. (verification: integration - add `tests/test_command_review_adapter.py` cases asserting no automatic `REVIEW_GAUNTLET` injection and asserting configured env values are visible to the fake command)
- [ ] Update command metadata artifacts to reflect prompt argv mode, inherited vs explicit cwd, configured timeout, output mode, stdout, stderr, verdict, and failure details without referencing removed `input_mode`. (verification: unit - update artifact assertions in `tests/test_command_review_adapter.py` to inspect `command.json` and prompt artifact files)
- [ ] Update CLI/session tests so command-adapter reviews use `{prompt}` configs, legacy configs fail clearly, adapter failures still keep cells unreviewed, and one `review` invocation still creates at most one run. (verification: integration - update `tests/test_cli_session_review.py` with success and failure configs using `{prompt}`)
- [ ] Update README and the repository self-review config `review-gauntlet.jsonc` to the minimal opencode `{prompt}` example, with optional `cwd`/`env`/`timeout_seconds` documented separately but not used in the standard example. (verification: manual - inspect `README.md` and `review-gauntlet.jsonc`; run `uv run pytest tests/test_config.py tests/test_command_review_adapter.py tests/test_cli_session_review.py`)
- [ ] Run the project quality gate after implementation. (verification: integration - `make check`)

## Future Work

- If a future CLI truly needs prompt files as a first-class transport again, propose a separate explicit feature instead of retaining the old implicit `prompt-file` mode.
- Real opencode smoke testing may require local opencode authentication and is outside automated verification.

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate. Expected archive gate: `cflx openspec validate simplify-command-adapter-prompt --archive-gate`.
