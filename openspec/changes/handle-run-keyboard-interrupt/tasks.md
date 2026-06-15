## Implementation Tasks

- [ ] Add a run-specific interrupted result path for `KeyboardInterrupt` in `src/review_gauntlet/cli.py` and/or `src/review_gauntlet/run_controller.py`. (verification: unit - add `tests/test_run_controller.py` coverage using a fake command runner that raises `KeyboardInterrupt` and assert the returned result has `completed: false`, `reason: interrupted`, a non-empty `error`, and the active `session_id`; completion condition: Ctrl-C no longer propagates to the Python entrypoint for the `run` path.)

- [ ] Preserve JSON output semantics for interrupted `run --format json`. (verification: integration - add `tests/test_cli.py` coverage that simulates interruption during `run --format json`, parses stdout with `json.loads`, asserts `reason == "interrupted"`, and asserts stdout/stderr do not contain `Traceback`; completion condition: automation can consume interrupted run output without special-casing Python tracebacks.)

- [ ] Preserve text output semantics for interrupted text-mode `run`. (verification: integration - add `tests/test_cli.py` coverage that simulates interruption during text-mode `run`, asserts a concise interrupted message or run summary is emitted, asserts no `Traceback` appears, and asserts exit code is non-zero; completion condition: human Ctrl-C reads like a handled interruption, not a crash.)

- [ ] Ensure session-level subprocess interruption is handled deterministically. (verification: unit - add `tests/test_run_controller.py` or `tests/test_cli.py` coverage using a fake or controlled command runner that raises `KeyboardInterrupt` while an active session remains, then assert no finalized result is reported and the active-session marker remains available; completion condition: the interrupted path cannot accidentally claim completion or hide the active session.)

- [ ] Keep existing run outcomes unchanged. (verification: integration - run existing `tests/test_cli.py` run scenarios plus any `tests/test_run_controller.py` scenarios for command failure, no-ready-task, max-step exhaustion, and successful finalization; completion condition: only the interrupt path changes behavior.)

- [ ] Run repository verification. (verification: integration - `make check`; completion condition: format, lint, typecheck, and tests pass under the repository's standard check command.)

## Future Work

- Consider adding consistent `KeyboardInterrupt` handling to other long-running commands if users report the same traceback behavior outside `run`.
- Add live subprocess cancellation telemetry if command execution is later changed from `subprocess.run` to streaming process management.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate handle-run-keyboard-interrupt --archive-gate`
