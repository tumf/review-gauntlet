## Implementation Tasks

- [x] Update command adapter configuration defaults and validation so `timeout_seconds` defaults to `3600.0`, `quiet_timeout_seconds` defaults to `600.0`, explicit configured values are preserved, and invalid quiet-timeout values are rejected. (verification: unit - update `tests/test_config.py` to assert the new defaults, explicit override behavior, and rejection of zero, negative, NaN, and infinite `adapter.quiet_timeout_seconds` values.)
- [x] Enforce quiet timeout in the session command runner without regressing live stdout/stderr capture: track the latest output timestamp while the subprocess runs, kill the subprocess when no output is observed for `quiet_timeout_seconds`, and keep the existing overall `timeout_seconds` kill path. (verification: integration - add `tests/test_cli_run.py` coverage with a local Python adapter that stays silent past a small quiet timeout and returns a persisted failure reason before the larger overall timeout.)
- [x] Preserve active-output behavior by resetting quiet-timeout liveness on both stdout and stderr output, including commands that run longer than the quiet timeout while periodically emitting output. (verification: integration - add `tests/test_cli_run.py` coverage with a local Python adapter that emits periodic output and completes successfully under a small `quiet_timeout_seconds` but before `timeout_seconds`.)
- [x] Represent quiet timeout as a distinct structured failure while keeping terminal TUI wording in the timeout family. (verification: unit - update `tests/test_run_controller.py` and `tests/test_run_tui.py` so `quiet_timeout` maps to a terminal timed-out lifecycle/display without being collapsed into command failure, max-step exhaustion, or generic failure.)
- [x] Expose quiet-timeout details in persisted command artifacts and run result diagnostics, including configured `quiet_timeout_seconds` and enough stdout/stderr tail evidence for diagnosis. (verification: integration - extend `tests/test_cli_run.py` to parse the run result or persisted artifacts and assert `reason`, quiet timeout seconds, and captured output fields are present.)
- [x] Update user-facing documentation for command adapter defaults and quiet timeout behavior. (verification: integration - repository-verifiable evidence is `README.md`, `README.ja.md`, `tests/test_config.py`, and `tests/test_cli_run.py`; runnable commands: `rg "timeout_seconds|quiet_timeout_seconds" README.md README.ja.md` and `uv run pytest tests/test_config.py tests/test_cli_run.py` verify the documented default `timeout_seconds` as 3600 seconds / 60 minutes and default `quiet_timeout_seconds` as 600 seconds / 10 minutes.)
- [x] Run the repository quality gate after implementation. (verification: integration - `make check` passed via agent-exec job `f0b2859c8ba89df4870235800152a243`.)

## Future Work

- Provider-specific guidance for intentionally silent agents can be added later if real-world adapters need longer quiet windows.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate set-run-timeouts --archive-gate`
