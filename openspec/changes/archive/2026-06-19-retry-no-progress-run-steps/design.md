# Design: no-progress retry loop

## Current behavior

`RunController.run` captures targeted cell/finding state before invoking the external command and compares it after a successful continuation verdict. If the verdict says `continue` or `finish` but the targeted state snapshot is unchanged, the controller rewrites the command result to a `no_progress` failure and returns immediately.

This prevents false completion, but it does not use the already-known diagnostic facts to help the external agent recover.

## Proposed behavior

Treat `no_progress` like an agent-correctable turn failure:

1. Keep the pre/post state comparison authoritative.
2. Continue producing a `no_progress` failure payload for the failed step.
3. If step budget remains, create a pending retry task from the same `ReadyTask` with an appended no-progress diagnostic section.
4. Emit `retry_scheduled` with `reason: no_progress`.
5. Re-enter the loop and execute the corrected prompt.
6. If the retry budget is exhausted, return the final `no_progress` failure exactly as a terminal structured result.

## Diagnostic content

The retry prompt should include:

- statement that the prior verdict was valid but made no targeted state change
- target IDs from the progress target
- task key and verdict path when available
- previous verdict value
- artifact context when available
- instruction to perform concrete state-changing commands before writing another verdict

## Safety properties

- The system still does not trust LLM self-report for completion.
- Incomplete state remains visible in `status`, `findings`, and final failure payloads.
- Retrying is bounded by the existing `max_steps` control.
- The retry remains scoped to the same ready task, so it does not broaden file or finding scope.
