---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_init_targets.py
  - tests/test_cli_session_review.py
  - openspec/specs/review-sessions/spec.md
---

# Fix zero-cell init next command

**Change Type**: implementation

## Problem / Context

`review-gauntlet init` currently emits `next_command: review-gauntlet review` unconditionally. When target filtering produces zero review cells, that command cannot perform review work: `review-gauntlet review` selects no cells, emits `run_id: null`, and does not create a run. The init output therefore guides developers toward a no-op even though the session has no promptable review work.

This violates the product principle that incomplete or absent coverage state should remain explicit rather than optimistic. The CLI should distinguish sessions with pending review cells from sessions whose selected target contains no reviewable cells.

## Proposed Solution

Make `review-gauntlet init` derive its next-command guidance from the initialized review cell count:

- If `cell_count > 0`, keep the current guidance: `next_command: review-gauntlet review`.
- If `cell_count == 0`, do not emit `review-gauntlet review` as the next command. Emit a machine-readable no-review-cells state instead, with `next_command` set to `null` in JSON output.
- Preserve the existing lifecycle distinction that init creates an active session without starting a run.

## Acceptance Criteria

- `init --format json` with one or more review cells still reports `session_state: active`, `run_state: none`, `run_count: 0`, and `next_command: review-gauntlet review`.
- `init --format json` with zero review cells reports `cell_count: 0`, `run_count: 0`, and does not report `review-gauntlet review` as `next_command`.
- Text output for zero-review-cell init does not suggest running `review-gauntlet review` as the next command.
- Existing target-selection behavior for `--worktree`, `--all`, `--from/--to`, `--commit`, and checkpoint defaults remains unchanged.
- `review` behavior for already-complete or no-selected-cell sessions remains unchanged by this proposal.

## Explicit Completion Conditions

- `_cmd_init` in `src/review_gauntlet/cli.py` derives init next-command output from `len(cells)` instead of using an unconditional fixed string.
- Tests cover both positive-cell and zero-cell init output contracts.
- The existing package-only worktree target test asserts that zero-cell init does not emit `review-gauntlet review` as `next_command`.
- Focused tests covering init output pass.
- `make check` passes.

## Out of Scope

- Changing whether zero-cell sessions can be finalized.
- Creating placeholder or empty review run records from `init` or `review`.
- Changing review inventory exclusion rules.
- Changing target selection or checkpoint-base behavior.
