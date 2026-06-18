# Design: Turn Verdict Validation

## Context

Review Gauntlet currently has two different verdict contracts:

- OCR review-cell verdicts, validated by `review-gauntlet validate-verdict`, with the shape `{"comments": [...]}`.
- Run-turn continuation verdicts, validated internally by `validate_continuation_verdict()`, with the shape containing `schema_version`, `verdict`, `summary`, finding ID lists, `resolutions`, `next_turn_instructions`, and `error`.

The runtime already validates continuation verdicts when processing agent output. The missing pieces are:

1. an agent-operable validation command that can be run before the agent ends its turn; and
2. a corrective runtime path that turns invalid verdict diagnostics into a bounded second attempt instead of immediately ending the whole run as `VERDICT INVALID`.

## Design Goals

- Keep OCR review verdict validation and run-turn verdict validation separate.
- Reuse the existing continuation schema and path-safety checks.
- Provide machine-readable output suitable for autonomous agents.
- Make generated prompts self-contained: the agent should see exactly which command to run for the exact file it must write.
- Catch both schema errors and, when possible, state-transition errors before runtime application.
- Treat invalid runtime verdicts as correctable agent output while retry budget remains.
- Bound invalid-verdict retries so repeated malformed output cannot loop forever.

## Proposed CLI Surface

Add:

```bash
review-gauntlet validate-turn-verdict <path> --format json
```

Expected success output:

```json
{
  "valid": true,
  "path": ".review-gauntlet/turns/RGS-test/open__aaaaaaaaaaaa.json",
  "verdict": "finish",
  "resolution_count": 2
}
```

Expected failure output:

```json
{
  "valid": false,
  "path": ".review-gauntlet/turns/RGS-test/open__aaaaaaaaaaaa.json",
  "error": "invalid continuation verdict schema: ..."
}
```

The command should exit `0` only for valid verdicts and non-zero for invalid verdicts.

## Validation Layers

1. File/path layer
   - Path exists.
   - Path remains under `.review-gauntlet/turns/<session-id>/`.
   - Filename has a valid continuation task-key shape.

2. Schema layer
   - JSON parses.
   - `ContinuationVerdict` validates.
   - `resolutions[].state` uses the canonical `FindingResolution` literals.

3. Ledger transition layer
   - If the repository has an active session and the referenced finding IDs exist, validate the requested transitions against current finding state.
   - Transition validation should not mutate the ledger.
   - Missing finding IDs should be reported as validation failures when active-session context is available.

## Runtime Invalid-Verdict Retry

If the external agent exits and the continuation file is present but invalid, the runtime should not immediately discard the opportunity to repair the output. Instead:

1. Capture the validation diagnostic, verdict path, and any relevant raw verdict artifact path.
2. Preserve the same file-scoped task and targeted finding IDs.
3. Render the next prompt for that same task with an explicit previous-invalid-verdict section containing the diagnostic.
4. Ask the agent to rewrite the same continuation file and validate it.
5. Consume retry/run budget.
6. If the retry bound is exhausted, return the existing terminal invalid-verdict failure shape with the last diagnostic and artifacts.

The retry state may be held in run-controller memory for the active `run` invocation. It does not need to become durable ledger truth because invalid verdicts do not change finding state or coverage.

## Prompt Integration

The existing continuation prompt section should add a short validation block after the required schema:

```text
After writing the turn verdict file, validate it before ending this turn:
review-gauntlet validate-turn-verdict <continuation_path> --format json
If validation fails, rewrite the verdict file and run the command again. Do not end this turn until validation returns valid=true.
```

When the previous attempt produced an invalid verdict, the next prompt should also include a diagnostic block such as:

```text
## Previous invalid turn verdict
The previous verdict file was invalid and must be corrected before doing other work.
path: <continuation_path>
error: <validation error>
```

This keeps the instruction colocated with the path and schema rather than relying on global agent memory.

## Error Handling

The validation command should mirror existing CLI conventions:

- Human text output for default text mode.
- JSON object output for `--format json`.
- Non-zero exit for validation failure.
- No source file mutations.
- No adapter subprocess execution.

The runtime retry path should preserve the existing terminal failure semantics after exhaustion. The change is only that invalid verdicts get a bounded correction opportunity before becoming terminal.

## Trade-offs

Using a separate command is more explicit than overloading `validate-verdict --kind turn`. It avoids ambiguity for agents and preserves existing OCR validation semantics.

Ledger transition validation is valuable because it catches verdicts that are schema-valid but still impossible to apply, such as a verdict whose resolution state is legal in general but illegal from the current finding state.

A bounded retry adds orchestration complexity, but it is preferable to requiring a human to restart the run for easily correctable JSON mistakes. The bound preserves the constitution's principle that unknown and failed states remain visible rather than hidden behind infinite retries.
