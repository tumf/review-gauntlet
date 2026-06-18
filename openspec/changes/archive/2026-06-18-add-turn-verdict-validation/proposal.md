---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/continuation.py
  - src/review_gauntlet/findings.py
  - tests/test_continuation.py
  - tests/test_cli_run.py
  - tests/test_run_controller.py
  - openspec/specs/review-sessions/spec.md
---

# Add Turn Verdict Validation

**Change Type**: implementation

## Problem/Context

`review-gauntlet run` requires continuation-aware finding turns to write a JSON turn verdict under `.review-gauntlet/turns/<session-id>/`. The runtime can detect invalid verdicts after the external agent exits, but the current behavior treats the invalid verdict as a failed run step instead of using the validation error as feedback for a bounded correction turn.

The existing `review-gauntlet validate-verdict` command validates OCR-style review-cell verdicts shaped as `{"comments": [...]}`. It does not validate run-turn continuation verdicts shaped with `schema_version`, `verdict`, `summary`, `completed_finding_ids`, `remaining_finding_ids`, and `resolutions`. In the observed failure, an agent wrote `resolutions[].state: "fixed"`; the runtime correctly identified the continuation verdict as invalid, but the useful diagnostic was surfaced only as a terminal `VERDICT INVALID` outcome rather than being fed back to the agent for a second attempt.

## Proposed Solution

Add a turn-verdict validation surface, require generated run/resolve prompts to instruct agents to use it before ending their turn, and make runtime invalid-verdict handling corrective rather than immediately terminal while bounded retry budget remains.

The implementation SHALL add a CLI command such as `review-gauntlet validate-turn-verdict <path> --format json` that validates the continuation verdict file with the existing continuation verdict schema and reports parseable success or failure. The command SHALL be distinct from OCR review verdict validation to avoid conflating the two JSON contracts.

The prompt section that tells agents where to write the continuation file SHALL also tell them to run the validation command after writing the file, rewrite the file if validation fails, and not end the turn until validation succeeds.

When runtime processing still observes an invalid continuation verdict, `run` SHALL preserve the active file-scoped task, include the invalid-verdict diagnostic in the next prompt for that same task, and invoke the agent again if retry budget remains. Retries SHALL be bounded by the existing run step budget and/or an explicit invalid-verdict retry counter so the same invalid verdict cannot loop indefinitely.

When session context is available, validation SHOULD also reject resolution states that cannot be applied from the current finding state, so an agent can catch transition errors before the runtime step tries to apply them.

## Acceptance Criteria

- A developer or external agent can run a documented CLI command to validate a turn continuation verdict file and receive JSON output with `valid: true` for valid verdicts.
- The same command exits non-zero and emits structured JSON with `valid: false` and an actionable error when the turn verdict schema is invalid, including invalid resolution states such as `"fixed"`.
- The command remains separate from `review-gauntlet validate-verdict`, which continues to validate OCR review-cell verdicts without behavior regression.
- Generated continuation-aware run/resolve prompts include the validation command using the exact continuation path for the current turn.
- Generated prompts instruct agents to fix and re-run validation when validation fails, and not to end the turn until validation succeeds.
- If an agent nevertheless exits with an invalid continuation verdict and retry budget remains, `run` starts a follow-up attempt for the same file-scoped task instead of terminating immediately.
- The follow-up prompt includes the invalid verdict diagnostic, the verdict path, and enough context for the agent to correct the JSON without guessing.
- Invalid-verdict retry attempts are bounded; when the bound is exhausted, `run` reports a terminal `invalid_step_verdict` / `verdict_invalid` style failure with the last diagnostic and artifact paths.
- When validating against an active session, impossible finding state transitions are rejected before the run controller tries to apply them.
- Tests cover successful validation, invalid verdict rejection, runtime invalid-verdict retry, and retry exhaustion, including the observed `"fixed"` resolution-state failure.
- Repository verification includes `make check`.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` exposes a session-safe turn verdict validation CLI command with `--format json` output.
- The new command reuses `validate_continuation_verdict()` from `src/review_gauntlet/continuation.py` rather than duplicating schema definitions.
- The command produces machine-readable success and failure payloads and exits non-zero on invalid verdicts.
- The continuation prompt generation path includes the validation command for the exact file path under `.review-gauntlet/turns/<session-id>/`.
- Runtime invalid-verdict handling stores or propagates an actionable diagnostic into the next prompt for the same file-scoped task when retry budget remains.
- The retry path consumes bounded run budget and cannot retry indefinitely on repeated invalid verdicts.
- Tests in `tests/test_continuation.py`, `tests/test_cli_run.py`, `tests/test_run_controller.py`, or adjacent modules prove valid turn verdicts pass, invalid turn verdicts can be retried with diagnostics, and repeated invalid verdicts eventually fail with a terminal bounded outcome.
- Tests prove `validate-verdict` remains OCR-verdict-specific and is not repurposed for turn verdicts.
- `cflx openspec validate add-turn-verdict-validation --strict --evidence warn` passes.
- `make check` passes.

## Out of Scope

- Changing the OCR review-cell verdict contract.
- Renaming or removing `review-gauntlet validate-verdict`.
- Rewriting the run TUI.
- Changing durable ledger schema beyond any minimal reads or transient retry state needed for transition validation and invalid-verdict retry.
- Silently accepting invalid aliases such as `"fixed"`; invalid state names should remain invalid and be corrected by a bounded retry.
