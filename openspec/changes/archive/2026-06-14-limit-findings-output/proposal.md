---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli_findings.py
  - openspec/specs/review-sessions/spec.md
  - skills/review-gauntlet/SKILL.md
---

# Limit findings output by default

**Change Type**: implementation

## Problem / Context

`review-gauntlet findings` currently returns every visible finding for the active session unless the caller narrows the result with `--path`, `--mark`, or terminal visibility via `--all`. Large sessions can produce very large JSON/text outputs, which is especially harmful for agent workflows that read findings into limited context.

The command must remain explicit about incompleteness: limiting output must not hide the existence of additional findings. The result therefore needs stable ordering plus count metadata that makes truncation visible.

## Proposed Solution

Add bounded findings listing behavior to `review-gauntlet findings`:

- Default `findings` output to at most 10 findings.
- Add `--limit N` to override the bounded result size with a positive integer.
- Add `--all-findings` to disable the result-size bound.
- Keep existing `--all` semantics unchanged: it controls terminal finding visibility only.
- Reject `--limit` together with `--all-findings` as a usage error.
- Always include `total` and `returned` counts in findings output.
- Return findings in deterministic path-first order: `path ASC, start_line ASC, end_line ASC, finding_id ASC`.
- Preserve existing non-mutating behavior: listing findings must not create runs or finding events.
- Update the review-gauntlet agent skill so agent guidance uses bounded findings output intentionally and uses `--all-findings` only when needed.

## Acceptance Criteria

- `review-gauntlet findings --format json` returns no more than 10 findings by default after visibility and filter rules are applied.
- `review-gauntlet findings --limit 3 --format json` returns no more than 3 findings.
- `review-gauntlet findings --all-findings --format json` returns all findings matching visibility and filter rules.
- `review-gauntlet findings --all --all-findings --format json` returns all findings including terminal findings.
- `--all` and `--all-findings` have independent meanings and neither replaces the other.
- `review-gauntlet findings --limit 3 --all-findings` fails with a usage error and exits with the project's usage error code.
- JSON output always includes `session_id`, `total`, `returned`, and `findings`.
- `total` is the number of findings after `--all`, `--path`, and `--mark` filtering but before result-size limiting.
- `returned` is the number of findings actually included in the `findings` array.
- Findings are returned in deterministic `path`, `start_line`, `end_line`, `finding_id` order.
- Existing `--path`, `--mark`, terminal suppression, `--all`, and non-mutating behavior continue to work.

## Explicit Completion Conditions

This change is complete when:

- `src/review_gauntlet/cli.py` exposes `--limit` and `--all-findings` on the `findings` subcommand and enforces the invalid combination before emitting results.
- The `_findings` result contains `total` and `returned` counts and applies deterministic sorting plus bounded result slicing according to the new flags.
- `tests/test_cli_findings.py` contains regression coverage for default limiting, explicit limiting, unlimited output, terminal visibility independence, invalid argument combinations, deterministic sorting, and count metadata.
- `skills/review-gauntlet/SKILL.md` documents bounded findings usage for agents and clarifies when to request `--all-findings`.
- `cflx openspec validate limit-findings-output --strict --evidence warn` passes.
- `uv run pytest tests/test_cli_findings.py` passes.
- `make check` passes, or any failure is unrelated and explicitly documented by the implementer.

## Out of Scope

- Adding a `--sort` CLI option.
- Adding offset/page-based pagination.
- Changing finding identity, lifecycle states, or mark transitions.
- Changing `status`, `ready`, `review`, `verify-fixes`, or `finalize` semantics.
- Optimizing findings storage schema or adding database indexes unless required to satisfy deterministic ordering efficiently.
