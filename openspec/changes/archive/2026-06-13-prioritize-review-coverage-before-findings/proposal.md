---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - tests/test_cli_ready.py
  - tests/test_cli_session_review.py
---

# Prioritize Review Coverage Before Findings

**Change Type**: implementation

## Problem / Context

`review-gauntlet` currently reports finding work as the next required action before unfinished review coverage. In a session with both pending review cells and untriaged findings, `status.next_required_action` returns `triage_findings`, and `ready` prompts agents to triage existing findings.

This interrupts the desired work sequence for review sessions: first complete the review universe coverage, then triage and fix findings produced by that complete coverage pass. The repository constitution treats coverage as a first-class product and requires unreviewed scope to stay visible, so orchestration should prefer closing pending or stale review cells before switching into finding triage.

## Proposed Solution

Update continuation priority so review coverage work is selected before finding-state work whenever current review cells remain pending or stale.

The new ordering for `status.next_required_action` and `ready` should be:

1. pending or stale review cells: run review work
2. target digest drift: run review work
3. reopened or untriaged findings: triage findings
4. confirmed findings: fix confirmed findings
5. fixed-pending findings: verify fixes
6. remaining finalize blockers: resolve blockers
7. no blockers: finalize

This preserves finalization blockers and finding counts while changing only the next-action ordering exposed to external orchestrators.

## Acceptance Criteria

- When a session has pending review cells and untriaged findings, `review-gauntlet status --format json` returns `next_required_action: run_review`.
- When a session has pending review cells and untriaged findings, `review-gauntlet ready --format json` returns a prompt instructing review of pending cells rather than finding triage.
- When all review cells are reviewed and untriaged or reopened findings remain, `status` and `ready` continue to request finding triage.
- Confirmed and fixed-pending finding workflows remain reachable after review coverage is complete.
- `finalize_blockers` remains conservative and still lists both unfinished coverage and live finding blockers when both exist.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` implements the new shared priority semantics for `_next_action()` and `_ready_prompt()`.
- Tests cover mixed pending-cell plus finding states for both `status` and `ready`.
- Existing priority tests are updated so coverage work is observed before finding work, and finding priority is still verified once coverage is complete.
- `make check` passes.
- `cflx openspec validate prioritize-review-coverage-before-findings --strict` passes.

## Out of Scope

- Changing finding state transitions, finding ID allocation, or triage semantics.
- Automatically running review loops until all cells complete.
- Changing finalization requirements; completion still requires both terminal coverage and terminal findings.
