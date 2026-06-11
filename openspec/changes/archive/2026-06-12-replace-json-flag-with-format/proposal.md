---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli.py
  - openspec/specs/review-sessions/spec.md
---

# Replace Legacy JSON Flag With Explicit Output Format

**Change Type**: implementation

## Problem / Context

The legacy `inventory` and `plan` commands currently define a `--json` flag, but the flag is not consulted at runtime: both commands always emit Pydantic JSON output. This makes the CLI contract misleading and prevents a human-oriented default output mode.

The desired CLI contract is explicit format selection: `--json` should be removed, `--format json|text` should be added to `inventory` and `plan`, and the default should become `text`.

## Proposed Solution

Update the legacy planning commands so `inventory` and `plan` accept `--format` with choices `json` and `text`, defaulting to `text`. Preserve the existing Pydantic JSON contracts under `--format json`, and add deterministic text renderers for the default human-oriented output.

The existing `report` command keeps its current `--format markdown|json` behavior, and session commands keep their existing `--format human|json` behavior.

## Acceptance Criteria

- `review-gauntlet inventory <root>` emits deterministic text output by default.
- `review-gauntlet plan <root>` emits deterministic text output by default.
- `review-gauntlet inventory <root> --format json` emits the same parseable inventory JSON contract currently produced by the legacy command.
- `review-gauntlet plan <root> --format json` emits the same parseable plan JSON contract currently produced by the legacy command.
- `review-gauntlet inventory <root> --json` and `review-gauntlet plan <root> --json` fail argument parsing instead of silently accepting the legacy flag.
- Existing `report --format markdown|json` behavior remains unchanged.
- Existing session command `--format human|json` behavior remains unchanged.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` no longer registers `--json` for `inventory` or `plan`.
- `src/review_gauntlet/cli.py` registers `--format` with choices `json` and `text` for `inventory` and `plan`, with `text` as the default.
- Text output paths for `inventory` and `plan` are covered by tests that assert deterministic human-readable output markers.
- JSON output paths for `inventory` and `plan` are covered by tests that parse stdout with `json.loads`.
- Legacy `--json` rejection is covered by tests for both `inventory` and `plan`.
- Project checks pass with `make check`.

## Out of Scope

- Changing `report` from `markdown|json` to `text|json`.
- Changing session workflow command formats from `human|json`.
- Changing inventory classification, review slice construction, or report matrix semantics.
