---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
  - openspec/specs/review-sessions/spec.md
---

# Align run TUI active checklist row with next required action

**Change Type**: implementation

## Problem / Context

`review-gauntlet status` exposes `next_required_action` as the authoritative next operation for an active session. The interactive `run` TUI currently derives the active `Finalize checklist` row from coverage, finding counts, and blockers independently of `next_required_action`.

This can make the TUI point at a different row than the action selected by the CLI. For example, when status reports stale coverage and fixed-pending findings together, `next_required_action` can be `run_verify_fixes` while the TUI highlights `Review coverage` because stale coverage is treated as the earliest incomplete finalize gate.

The TUI should remain human-facing and avoid raw internal action names, but the active checklist row and header should be driven by the same next-action source used by the rest of the workflow.

## Proposed Solution

Update the run TUI view-model derivation so known `next_required_action` values select the active `Finalize checklist` row:

- `run_review` -> `Review coverage`
- `triage_findings` -> `Triage findings`
- `fix_confirmed_findings` -> `Fix confirmed findings`
- `run_verify_fixes` -> `Verify fixes`
- `resolve_finalize_blockers` -> `Final checks`
- `finalize` -> `Finalize checkpoint`
- `cleanup_git_worktree` -> `Finalize checkpoint`

The TUI SHALL keep the six existing checklist rows and human-facing labels. It SHALL keep row details grounded in coverage, finding, and blocker data so incomplete coverage or unresolved findings remain visible even when `next_required_action` points to a later operation. Unknown or missing `next_required_action` values SHALL fall back to the existing derived checklist behavior.

## Acceptance Criteria

- The `run` TUI header current gate, Session `Current` row, and `Finalize checklist` active row agree with known `next_required_action` values.
- A session with `coverage.stale > 0`, fixed-pending findings, and `next_required_action: run_verify_fixes` highlights `Verify fixes` as the current checklist row while still showing stale coverage in the checklist details.
- TUI output continues to hide raw internal action names such as `run_verify_fixes`, `run_review`, and `resolve_finalize_blockers`.
- The existing six-row `Finalize checklist` structure, row labels, and allowed state labels remain unchanged.
- Unknown or absent `next_required_action` values preserve the current fallback gate derivation behavior.

## Explicit Completion Conditions

- `src/review_gauntlet/run_tui.py` maps known `RunSnapshot.next_required_action` values to checklist gate indices or equivalent view-model selection logic.
- `derive_finalize_gates(...)` or its replacement keeps row details based on actual session data and does not mark incomplete data invisible solely because the active action points elsewhere.
- `tests/test_run_tui.py` includes regression coverage for `run_verify_fixes` taking precedence over stale coverage for active-row selection.
- `tests/test_run_tui.py` includes coverage for at least `run_review`, `resolve_finalize_blockers`, `finalize`, and unknown-action fallback behavior.
- `make check` passes.

## Out of Scope

- Changing `review-gauntlet status` action selection semantics.
- Changing ready-prompt generation or command adapter execution order.
- Renaming the `Finalize checklist` panel or changing the six checklist row titles.
- Implementing source-code changes as part of this proposal commit.
