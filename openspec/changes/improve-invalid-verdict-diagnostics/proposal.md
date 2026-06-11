---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/review_adapter.py
  - src/review_gauntlet/cli.py
  - tests/test_review_adapter.py
  - tests/test_cli.py
  - openspec/specs/review-sessions/spec.md
---

# Improve Invalid Verdict Diagnostics

**Change Type**: implementation

## Problem / Context

External command adapters can write malformed verdict JSON. In the observed failure, `opencode run` wrote `.review-gauntlet/runs/2/cells/RGC-6441eaf3b1a748b6/verdict.json` with Python-style single-quoted string values, which is invalid JSON. `review-gauntlet` correctly rejected the verdict and left the failed cell unreviewed, preserving coverage truth.

However, the reported failure only surfaced `invalid verdict JSON`, a Pydantic validation message, and the output mode. It did not include the verdict artifact path, raw artifact path, parse location context, or a bounded snippet showing the offending text. Users had to inspect run artifacts manually to determine that the adapter wrote invalid JSON.

## Proposed Solution

Keep malformed adapter verdicts as hard failures, but make the failure actionable. When verdict parsing fails, `review-gauntlet` should include diagnostic metadata in `failure.json` and the CLI failure payload so users and agents can immediately locate and inspect the bad adapter output.

The diagnostics should include artifact paths, output mode, a bounded raw snippet around the parse failure when available, and a concise hint that the adapter must write strict JSON. The implementation must not silently repair malformed verdicts or mark the cell reviewed.

## Acceptance Criteria

- Invalid verdict JSON failures include `output_mode`, `verdict_path`, `raw_verdict_path`, and a bounded `raw_snippet` in `failure.json`.
- The CLI failure payload for `review` includes the same actionable failure metadata through the existing `failure` field.
- Diagnostics identify enough context to distinguish adapter output errors from `review-gauntlet` parser bugs without requiring users to manually guess artifact locations.
- Malformed verdicts remain hard failures and do not mark the failed cell as `reviewed`.
- Valid verdict parsing behavior and normalized `verdict.json` writing remain unchanged.
- No automatic JSON repair, quote conversion, or best-effort acceptance is performed.

## Explicit Completion Conditions

- `src/review_gauntlet/review_adapter.py` enriches invalid verdict JSON failures with artifact paths and bounded raw-output context.
- The enriched failure payload is persisted in `.review-gauntlet/runs/<run>/cells/<cell>/failure.json` and propagated through `ReviewAdapterError.failure` to CLI output.
- Tests cover malformed file-json output with single-quoted strings and assert that the failure metadata contains paths and a raw snippet while the cell remains unreviewed.
- Tests cover malformed stdout-json output so both output modes receive equivalent diagnostics.
- Existing tests for successful adapter verdicts continue to pass.
- `make check` passes.

## Out of Scope

- Automatically repairing malformed JSON produced by external adapters.
- Retrying failed cells automatically.
- Changing the OCR verdict schema or finding normalization contract.
- Changing external adapter prompts beyond diagnostic-oriented hints that do not alter the verdict contract.
- Changing review progress display or cancellation behavior.
