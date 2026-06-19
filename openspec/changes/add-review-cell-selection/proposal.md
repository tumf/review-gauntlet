---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/review_cells.py
  - src/review_gauntlet/session_store.py
  - tests/test_cli_session_review.py
  - tests/test_cli.py
  - openspec/specs/review-sessions/spec.md
---

# Add Review Cell Selection

**Change Type**: implementation

## Premise / Context

- The inferred request is to add a required way for `review-gauntlet review` users to specify review cells explicitly when they want a targeted review run.
- `review-gauntlet review` currently accepts budget, parallelism, fixture/config, format, and audience options, but no cell selector.
- Review cells are durable session coverage units identified by `RGC-*` IDs and selected from the reconciled active session before adapter invocation.
- The project constitution requires unreviewed state to stay visible and requires one `review` command to advance exactly one review phase.
- This change is implementation-facing because it affects CLI parsing, review-cell selection, status output behavior, and tests.

## Problem / Context

Developers can inspect active review cells through session status and related outputs, but `review-gauntlet review` currently selects every pending cell for Phase 1 execution. When users need to retry, debug, or constrain a run to one or more known cells, they must rely on broad selection controls rather than naming the intended coverage units directly.

Without explicit cell selection, targeted review work is harder to reproduce and harder to keep bounded. This is especially painful for command adapters that may be slow, expensive, or produce large artifacts.

## Proposed Solution

Add a repeatable `--cell <cell-id>` option to `review-gauntlet review`. When one or more cell IDs are supplied, the command SHALL restrict the run's eligible review cells to those IDs after reconciling the active session and before invoking the review adapter.

The option should preserve existing behavior when omitted. It should be deterministic, should not hide unknown or already-reviewed coverage, and should return actionable usage errors for unknown requested cell IDs before adapter work starts.

## Acceptance Criteria

- `review-gauntlet review --cell RGC-...` accepts one or more explicitly requested review cell IDs.
- When `--cell` is omitted, `review-gauntlet review` keeps the existing all-pending-cell behavior.
- When `--cell` is supplied, only requested cells that are currently pending are passed to the review adapter.
- Requested cells that are already reviewed are not re-reviewed and remain visible through normal status output.
- Requested cell IDs that are not part of the active reconciled session fail before adapter invocation with usage-error semantics and a diagnostic naming the unknown IDs.
- Duplicate `--cell` values do not cause duplicate adapter invocations.
- Existing `--budget` and `--parallel` behavior remains compatible with explicit cell selection.
- JSON output remains parseable and continues to include run/status fields consistent with existing review output.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` exposes repeatable `--cell` parsing for the `review` subcommand.
- Review selection first reconciles and enumerates current target cells, validates requested cell IDs against that universe, de-duplicates requested IDs deterministically, and then filters pending cells before adapter execution.
- Unknown requested cell IDs fail with exit code `64` and no new run/adaptor artifacts.
- Tests cover targeted single-cell execution, multiple/duplicate selectors, already-reviewed requested cells, unknown requested cells, and no-selector backward compatibility.
- `make check` passes.

## Out of Scope

- Adding file-path, rule-id, slice-id, glob, or state filter options.
- Re-reviewing cells that are already `REVIEWED`.
- Changing review cell identity, reconciliation semantics, finding persistence, or resolve/finalize behavior.
- Making `review-gauntlet run` accept cell selectors for its Phase 1 orchestration.
