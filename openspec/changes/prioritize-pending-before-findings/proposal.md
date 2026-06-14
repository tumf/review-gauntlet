---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - tests/test_cli_ready.py
  - tests/test_cli_session_review.py
---

# Prioritize Pending Review Before Finding Work

**Change Type**: implementation

## Problem / Context

`review-gauntlet` exposes continuation work through `status.next_required_action` and `ready`. The desired agent workflow is to avoid interrupting the first coverage pass: review all never-reviewed pending cells first, then process findings, then handle stale or verification review caused by fixes.

Treating all incomplete coverage equally is inefficient. Fixing confirmed findings can intentionally change files and stale previously reviewed cells. If stale cells are always prioritized before finding work, agents can spend effort refreshing stale coverage before fixes create more stale coverage, causing extra review passes.

## Proposed Solution

Change continuation priority from broad coverage-first ordering to pending-first phase ordering:

1. `pending` review cells: run review work
2. target digest drift: run review work for externally changed target state
3. `reopened` or `untriaged` findings: triage findings
4. `confirmed` findings: fix confirmed findings
5. `fixed_pending_verification` findings: verify fixes
6. `stale` review cells: run review work after finding/fix work has been resolved
7. remaining finalize blockers: resolve blockers
8. no blockers: finalize

This keeps initial coverage completion efficient while still preserving explicit visibility of stale coverage and all live findings in `finalize_blockers`.

## Acceptance Criteria

- When a session has pending review cells and untriaged findings, `review-gauntlet status --format json` returns `next_required_action: run_review`.
- When a session has pending review cells and untriaged findings, `review-gauntlet ready --format json` prompts review of pending cells rather than finding triage.
- When a session has stale review cells and untriaged or reopened findings, `status` and `ready` request finding triage before stale review.
- When a session has stale review cells and confirmed findings, `status` and `ready` request fixing confirmed findings before stale review.
- When a session has stale review cells and fixed-pending findings, `status` and `ready` request fix verification before generic stale review.
- When only stale review cells remain among continuation work, `status` returns `run_review` and `ready` prompts stale review.
- `finalize_blockers` remains conservative and lists all incomplete coverage and live finding blockers, even when the selected next action is only one phase.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` implements the pending-first continuation order consistently for `_next_action()` and `_ready_prompt()`.
- Tests cover mixed pending/finding states where pending review wins.
- Tests cover mixed stale/finding states where finding work wins before stale review.
- Tests cover stale-only continuation work where stale review remains reachable.
- Existing verification behavior for `fixed_pending_verification` findings remains intact.
- `make check` passes.
- `cflx openspec validate prioritize-pending-before-findings --strict` passes.

## Out of Scope

- Changing how cells become stale.
- Changing how fixed findings are verified or reopened.
- Automatically looping review commands until all phases complete.
- Changing finalization requirements; completion still requires terminal coverage and terminal findings.
