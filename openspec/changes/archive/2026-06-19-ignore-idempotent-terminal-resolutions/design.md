# Design: Ignored Idempotent Terminal Resolutions

## Requested Artifact

Implementation proposal with spec deltas.

## Scope Decision

This remains one proposal because validation classification, verdict application, and run-controller no-progress behavior must agree on the same notion of an ignored stale/idempotent resolution. Splitting these would risk one layer accepting no-op resolutions while another layer still treats them as progress or fatal errors.

## Behavior Model

Turn verdict resolution handling should classify each requested finding resolution into one of four categories:

1. `valid_transition`: current state can transition to requested state under `ALLOWED_TRANSITIONS`.
2. `idempotent_terminal_noop`: current state is terminal and requested state equals current state.
3. `unknown_finding`: the finding ID is not present in the active session.
4. `invalid_transition`: requested state is not allowed and is not an idempotent terminal no-op.

Only `valid_transition` should mutate finding state. `idempotent_terminal_noop` should be recorded or reported as ignored evidence. `unknown_finding` and `invalid_transition` should remain failures.

## Diagnostics

Diagnostics should remain explicit enough for the user to distinguish agent mistakes from stale artifacts:

- `invalid_transition` diagnostics should preserve current behavior: finding ID, current state, requested state, attempted transition, and allowed target states or terminal-state explanation.
- `idempotent_terminal_noop` diagnostics should be non-fatal but visible in structured output, run metadata, continuation metadata, or lifecycle context.
- If validation can infer a session ID from the turn verdict path, and it differs from the active session ID used for validation, the diagnostic should include both values.

## Run Controller Interaction

Ignored no-op resolutions are not progress. The run controller's existing no-progress guard should continue to compare targeted state before and after a step. A step whose only apparent work is ignored no-op resolutions should stop with `reason: no_progress` and preserved artifact context rather than repeat.

## Compatibility

This proposal does not relax the finding state machine. It only changes how exact duplicate terminal requests are classified. Meaning-changing terminal requests remain invalid, and open findings still use only `confirmed` or `dismissed` in the resolution phase.
