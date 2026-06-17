## Implementation Tasks

- [x] Add validated hook config models to `src/review_gauntlet/config.py`, including supported event-name validation, argv-style command validation, timeout validation, cwd/env template validation, and default empty hooks. (verification: unit - `uv run pytest tests/test_config.py` includes valid hooks, unknown event rejection, command whitespace rejection, invalid env rejection, and effective-config JSON assertions)
  Completion condition: `ReviewGauntletConfig` accepts configs without hooks unchanged and serializes a valid `hooks` mapping when configured.

- [x] Implement hook template context expansion for supported event fields and repository paths without permitting unsupported template variables. (verification: unit - `uv run pytest tests/test_config.py tests/test_cli_run.py` includes hook template assertions for `{event_type}`, `{timestamp}`, `{repo_root}`, `{state_dir}`, `{session_id}`, `{step}`, `{reason}`, and `{returncode}` expanding deterministically or to empty strings when absent)
  Completion condition: invalid hook templates fail before command execution, and valid templates produce expected argv/cwd/env values.

- [x] Add hook command execution for `review-gauntlet run` lifecycle events while excluding `status_refreshed` from hook dispatch. (verification: integration - `uv run pytest tests/test_cli_run.py` includes a fixture command or local Python hook proving a configured `run_started` or `finalized` hook executes during `review-gauntlet run`)
  Completion condition: hooks run only for supported configured events and run in declaration order for each event.

- [x] Persist hook execution artifacts under `.review-gauntlet` with stdout, stderr, argv, event type, return code, timeout/failure details, and artifact metadata. (verification: integration - `uv run pytest tests/test_cli_run.py` asserts hook artifact files exist and contain evidence from a real hook command)
  Completion condition: every attempted hook command has inspectable artifact metadata even when it exits non-zero or times out.

- [x] Provide event context to hook commands through environment variables, including full event JSON. (verification: integration - `uv run pytest tests/test_cli_run.py` uses a hook command that writes `REVIEW_GAUNTLET_EVENT_JSON` or related scalar env values to an artifact and asserts the payload matches the emitted event)
  Completion condition: hook subprocesses receive event JSON, event type, repo root, and state dir without exposing secrets or mutating unrelated environment values beyond configured env overlays.

- [x] Keep hook failures best-effort so missing commands, non-zero exits, and hook timeouts do not mask or change the primary run result. (verification: integration - `uv run pytest tests/test_cli_run.py` covers a failing hook alongside a successful run and asserts the run result still reports the correct primary completion or failure reason)
  Completion condition: hook diagnostics are visible in artifacts or stderr, while session state, run result, and exit behavior remain determined by review-gauntlet's primary workflow.

- [x] Compose hook dispatch with existing run-controller event sinks so TUI event rendering and controller event history continue to work. (verification: unit - `uv run pytest tests/test_run_controller.py tests/test_run_tui.py` continues to pass, and a focused test proves multiple sinks observe the same event when applicable)
  Completion condition: adding hooks does not replace or suppress existing `RunEvent` storage or TUI event display behavior.

- [x] Update bundled config presets or preset comments to keep examples valid and discoverable without enabling hooks by default. (verification: integration - `uv run review-gauntlet config preset show opencode` and `uv run review-gauntlet config validate --config <generated preset copy>` continue to work)
  Completion condition: all presets remain valid JSONC and document optional hooks only as opt-in examples.

- [x] Run repository checks after implementation. (verification: integration - `make check` passes)
  Completion condition: format, lint, typecheck, and tests all pass under the repository's standard check command.

## Future Work

- Optional future support for high-frequency events such as `status_refreshed` may be considered only with explicit throttling or opt-in safeguards.
- Optional remote webhook helpers are excluded from this local command hook change.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-configurable-run-hooks --archive-gate`
