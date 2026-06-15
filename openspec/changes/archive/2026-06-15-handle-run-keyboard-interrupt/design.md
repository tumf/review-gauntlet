# Design: Run interrupt handling

## Current Behavior

`review-gauntlet run` delegates orchestration to `RunController.run()`. The controller eventually calls a command runner that uses `subprocess.run(...)`. If a user presses Ctrl-C while the process is blocked, `KeyboardInterrupt` can escape to `main()` because the top-level command dispatch catches configuration and value errors but not user interrupts.

That produces a Python traceback for an ordinary CLI interrupt.

## Desired Behavior

Ctrl-C during `review-gauntlet run` should be treated as an explicit interrupted run outcome:

```json
{
  "completed": false,
  "reason": "interrupted",
  "error": "run interrupted by user",
  "steps": [],
  "step_count": 0,
  "session_id": "RGS-..."
}
```

The exact `steps` content may include any completed steps before interruption. It must not claim finalization unless the active session is actually gone.

## Implementation Approach

The narrowest implementation is to catch `KeyboardInterrupt` at the `run` command boundary, where output format and exit behavior are known. This keeps non-run commands unchanged and allows JSON/text output to reuse the normal `_emit_run` path.

A controller-level helper may also be useful so tests can exercise interruption without invoking the full CLI. The command runner injection seam already makes this practical: a fake command runner can raise `KeyboardInterrupt` and the controller or CLI boundary can convert that into an interrupted result.

## Subprocess Considerations

Python's `subprocess.run(...)` generally propagates `KeyboardInterrupt` when the user interrupts the parent process. The implementation should avoid swallowing the signal in a way that leaves the CLI pretending work succeeded. If deeper cancellation is needed, the command execution helper can translate interruption into a `SessionCommandResult` failure with `reason: interrupted`, but it must still preserve non-zero run completion semantics.

## Compatibility

- Existing JSON result shape is preserved.
- Existing text run rendering can render the interrupted result using the same `_emit_run` helper.
- Existing non-interrupt failure cases remain unchanged.
- The active session remains recoverable after interruption.

## Testing Strategy

- Unit test the controller or command-runner interrupt path with an injected fake command runner.
- Integration test CLI JSON mode by simulating interruption and parsing stdout.
- Integration test CLI text mode by simulating interruption and asserting no traceback.
- Run the existing CLI run tests to prove no regression in normal outcomes.
