---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/config.py
  - src/review_gauntlet/review_adapter.py
  - tests/test_command_review_adapter.py
  - review-gauntlet.jsonc
---

# Default command adapter verdicts to file-json

**Change Type**: implementation

## Problem / Context

The command adapter currently defaults to `stdout-json`. During real `review-gauntlet review` execution with the opencode adapter, opencode returned a natural-language preface followed by a valid JSON object. Because `stdout-json` requires stdout to be exactly one verdict JSON object, the review run failed with `invalid verdict JSON` even though the useful verdict payload was present.

This behavior is likely for agent-style CLIs that use stdout for progress, reasoning summaries, or incidental text. Review coverage should depend on the deterministic verdict artifact, not on whether an external agent keeps stdout perfectly clean.

## Proposed Solution

Make `file-json` the default command adapter output mode. When the output path is not explicitly configured, the adapter SHALL use the per-cell `{output_file}` artifact path. For `file-json`, stdout and stderr SHALL remain preserved as audit logs but SHALL NOT be parsed or trusted as verdict input.

The generated review prompt SHALL clearly instruct the external command to write the verdict JSON to the configured output file and treat stdout/stderr as non-verdict channels. Existing explicit `stdout-json` configurations SHALL remain supported for tools that can guarantee clean stdout.

## Acceptance Criteria

- A command adapter config that omits `adapter.output` defaults to `file-json` using the deterministic per-cell `verdict.json` output path.
- A `file-json` review succeeds when the command writes valid verdict JSON to the output file, even if stdout contains non-JSON text.
- A `file-json` review fails when the output file is missing or invalid, regardless of stdout content.
- Existing explicit `stdout-json` configs continue to parse stdout exactly as before.
- Per-cell artifacts continue to preserve prompt, command metadata, stdout, stderr, raw verdict, normalized verdict, and failure details.
- The sample `review-gauntlet.jsonc` demonstrates the default file-json workflow rather than stdout-json.

## Explicit Completion Conditions

- `src/review_gauntlet/config.py` defaults command output mode to file-json and permits omitted output paths by resolving them to the per-cell output artifact.
- `src/review_gauntlet/review_adapter.py` resolves omitted file-json output paths to the deterministic cell `verdict.json`, ignores stdout for verdict parsing in file-json mode, and records command metadata showing the effective output mode/path.
- `build_review_prompt()` includes an output contract suitable for file-json adapters, including the target output file location when available.
- `tests/test_command_review_adapter.py` includes regression tests for omitted output config, stdout noise in file-json mode, missing output file failure, and explicit stdout-json compatibility.
- `review-gauntlet.jsonc` no longer configures stdout-json as the recommended default.
- `make check` passes.

## Out of Scope

- Removing `stdout-json` support.
- Salvage parsing mixed stdout text plus JSON.
- Changing external opencode configuration, credentials, or model routing.
- Changing review-session triage semantics or finding normalization beyond command verdict transport.
