# Design: Invalid Verdict Diagnostics

## Current Behavior

The command adapter reads verdict text from stdout for `stdout-json` mode or from the configured output file for `file-json` mode. It writes `verdict.raw.json`, then validates the text with `VerdictPayload.model_validate_json`. On validation failure, it records a generic `invalid verdict JSON` failure with the validation error and output mode.

That preserves safety, but it does not give enough context to quickly debug adapter failures.

## Design Goals

- Keep strict JSON validation as the source of truth.
- Make adapter-output failures actionable from the CLI result and `failure.json`.
- Keep diagnostics bounded and safe for terminal output.
- Avoid silent repair or best-effort acceptance of malformed adapter output.

## Diagnostic Payload

Invalid verdict JSON failures should include:

- `error`: parser or validation message
- `output_mode`: `file-json` or `stdout-json`
- `verdict_path`: the configured final verdict output path for file output, or the normalized verdict artifact path for stdout output
- `raw_verdict_path`: path to `verdict.raw.json`
- `raw_snippet`: bounded raw text context useful for seeing malformed syntax
- `hint`: concise instruction that external adapters must write strict JSON using double-quoted strings and no markdown fences

The raw snippet should be bounded to avoid flooding CLI output. It may be a prefix if precise parser offsets are not available, or a contextual excerpt around a detected location when the parser exposes one.

## Trust Boundary

The adapter verdict is an untrusted external-tool output. Diagnostics may help a human fix the adapter or prompt, but `review-gauntlet` must not convert Python literals, strip markdown fences, or otherwise repair malformed verdicts in this change. Accepting repaired data would blur the boundary between adapter behavior and recorded review truth.

## Verification Strategy

Tests should use local malformed outputs, not real LLM calls. One fixture should mirror the observed failure with single-quoted `existing_code` or `suggestion_code` values. Both `file-json` and `stdout-json` output modes should be covered.
