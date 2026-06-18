## Implementation Tasks

- [ ] Update `RunController.run` no-progress handling to schedule a retry of the same `ReadyTask` when `step_number < max_steps`. Completion condition: a `SessionCommandResult` failure with `reason: no_progress` no longer returns immediately while retry budget remains. (verification: unit - `uv run pytest tests/test_run_controller.py::test_run_controller_retries_no_progress_with_diagnostic`)

- [ ] Add a dedicated no-progress diagnostic prompt helper that appends actionable correction guidance without replacing the original ready prompt. Completion condition: the second prompt includes a `## Previous no-progress turn` section naming the verdict path or task key, target IDs, verdict value, and available artifact context. (verification: unit - assertions in `tests/test_run_controller.py::test_run_controller_retries_no_progress_with_diagnostic` fail if the prompt omits the diagnostic details.)

- [ ] Preserve bounded failure behavior for repeated no-progress turns. Completion condition: when every retry still produces no targeted state change and `max_steps` is exhausted, `run` returns `completed: false` with `reason: no_progress` and the final no-progress failure payload remains visible. (verification: unit - `uv run pytest tests/test_run_controller.py::test_run_controller_bounds_repeated_no_progress_retries`)

- [ ] Keep existing invalid-turn-verdict retry behavior unchanged. Completion condition: existing invalid verdict retry tests continue to pass and retry diagnostics remain labelled as invalid verdict diagnostics. (verification: unit - `uv run pytest tests/test_run_controller.py::test_run_controller_retries_invalid_step_verdict_with_diagnostic tests/test_run_controller.py::test_run_controller_bounds_repeated_invalid_step_verdict_retries`)

- [ ] Run full project verification after implementation. Completion condition: formatting, linting, type checking, and tests all pass under the repository CI-equivalent command. (verification: integration - `make check`)

## Future Work

- Consider adding a retry-count field to structured run output if users need richer telemetry beyond the existing step list and retry events.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate retry-no-progress-run-steps --archive-gate`
