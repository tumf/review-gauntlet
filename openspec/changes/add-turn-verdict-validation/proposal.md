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
  - openspec/specs/review-sessions/spec.md
---

# Add Turn Verdict Validation

**Change Type**: implementation

## Problem/Context

`review-gauntlet run` requires continuation-aware finding turns to write a JSON turn verdict under `.review-gauntlet/turns/<session-id>/`. The runtime can detect invalid verdicts after the external agent exits, but the agent prompt does not provide a stable command for the agent to validate the turn verdict before ending its turn.

The existing `review-gauntlet validate-verdict` command validates OCR-style review-cell verdicts shaped as `{"comments": [...]}`. It does not validate run-turn continuation verdicts shaped with `schema_version`, `verdict`, `summary`, `completed_finding_ids`, `remaining_finding_ids`, and `resolutions`. In the observed failure, an agent wrote `resolutions[].state: "fixed"`; the runtime correctly rejected it as an invalid continuation verdict only after the agent had already completed.

## Proposed Solution

Add a turn-verdict validation surface and require generated run/resolve prompts to instruct agents to use it before ending their turn.

The implementation SHALL add a CLI command such as `review-gauntlet validate-turn-verdict <path> --format json` that validates the continuation verdict file with the existing continuation verdict schema and reports parseable success or failure. The command SHALL be distinct from OCR review verdict validation to avoid conflating the two JSON contracts.

The prompt section that tells agents where to write the continuation file SHALL also tell them to run the validation command after writing the file, rewrite the file if validation fails, and not end the turn until validation succeeds.

When session context is available, validation SHOULD also reject resolution states that cannot be applied from the current finding state, so an agent can catch transition errors before the runtime step fails.

## Acceptance Criteria

- A developer or external agent can run a documented CLI command to validate a turn continuation verdict file and receive JSON output with `valid: true` for valid verdicts.
- The same command exits non-zero and emits structured JSON with `valid: false` and an actionable error when the turn verdict schema is invalid, including invalid resolution states such as `"fixed"`.
- The command remains separate from `review-gauntlet validate-verdict`, which continues to validate OCR review-cell verdicts without behavior regression.
- Generated continuation-aware run/resolve prompts include the validation command using the exact continuation path for the current turn.
- Generated prompts instruct agents to fix and re-run validation when validation fails, and not to end the turn until validation succeeds.
- When validating against an active session, impossible finding state transitions are rejected before the run controller tries to apply them.
- Tests cover both successful validation and invalid verdict rejection, including the observed `"fixed"` resolution-state failure.
- Repository verification includes `make check`.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` exposes a session-safe turn verdict validation CLI command with `--format json` output.
- The new command reuses `validate_continuation_verdict()` from `src/review_gauntlet/continuation.py` rather than duplicating schema definitions.
- The command produces machine-readable success and failure payloads and exits non-zero on invalid verdicts.
- The continuation prompt generation path includes the validation command for the exact file path under `.review-gauntlet/turns/<session-id>/`.
- Tests in `tests/test_continuation.py`, `tests/test_cli_run.py`, or adjacent modules prove valid turn verdicts pass and invalid turn verdicts fail before agent completion.
- Tests prove `validate-verdict` remains OCR-verdict-specific and is not repurposed for turn verdicts.
- `cflx openspec validate add-turn-verdict-validation --strict --evidence warn` passes.
- `make check` passes.

## Out of Scope

- Changing the OCR review-cell verdict contract.
- Renaming or removing `review-gauntlet validate-verdict`.
- Rewriting the run controller lifecycle or TUI.
- Changing durable ledger schema beyond any minimal reads needed for transition validation.
- Silently accepting invalid aliases such as `"fixed"`; invalid state names should remain invalid.
