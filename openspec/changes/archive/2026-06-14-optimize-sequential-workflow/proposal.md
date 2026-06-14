---
change_type: implementation
priority: medium
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - tests/test_cli_session_review.py
---

# Optimize Sequential Workflow Execution

**Change Type**: implementation

## Problem / Context

Developers use `review-gauntlet status` and `review-gauntlet ready` to decide the next continuation step for an active review session. The current workflow must remain explicit about stale coverage, target digest drift, dirty review-universe files, and live findings, but the action ordering should avoid wasted review work when finding fixes are already in progress.

A session can simultaneously have stale coverage, target digest drift, confirmed findings, fixed-pending findings, and dirty review-universe files. If the CLI prioritizes stale or whole-target review work before resolving live findings, developers may re-review changed cells before applying known fixes, only to make the review evidence stale again after those fixes. The workflow should instead move already-in-progress finding work forward before generic stale/digest refresh work when doing so preserves correctness.

## Proposed Solution

Update session continuation policy so `status.next_required_action` and `ready` prioritize efficient sequential progress:

- Pending current review cells remain first, because they represent never-reviewed current target work.
- Reopened and untriaged findings remain ahead of implementation work, because they require classification before fixing.
- Confirmed findings are exposed before generic stale review refresh when no pending current cells remain.
- Fixed-pending findings are exposed before generic stale review refresh when no pending current cells remain.
- Generic stale coverage and whole-target digest refresh run after live finding work is exhausted, unless pending current cells require review.
- Dirty review-universe blockers remain finalize blockers and become actionable only after review/finding continuation work is exhausted.

This preserves the constitution's coverage and freshness guarantees while reducing re-review churn during fix-driven workflows.

## Acceptance Criteria

- `status --format json` reports finding-resolution work before generic stale review work when current target cells have no pending entries but do have stale entries and live confirmed findings.
- `status --format json` reports fixed-finding verification before generic stale review work when current target cells have no pending entries but do have stale entries and fixed-pending findings.
- `ready` emits matching continuation prompts for confirmed or fixed-pending findings before stale review prompts in the same conditions.
- Pending current review cells continue to produce review work before finding work.
- Whole-target digest drift alone does not force review ahead of live finding work when current cell coverage is otherwise complete or only fix-driven stale handling should happen after finding work.
- Finalization remains blocked until stale coverage, target digest drift, dirty review-universe files, and live findings are all resolved.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` computes `next_required_action` and `ready` continuation prompts with pending review first, live finding work before generic stale review, and finalize only after all continuation work is exhausted.
- CLI tests in `tests/test_cli_session_review.py` or equivalent cover the priority order for stale-plus-confirmed, stale-plus-fixed-pending, pending-plus-findings, and finalize blocker preservation.
- `uv run pytest tests/test_cli_session_review.py` passes for the focused behavior.
- `make check` passes before the change is considered ready to land.

## Out of Scope

- Automatically looping `review-gauntlet review` until completion.
- Automatically fixing findings, committing source changes, or finalizing sessions.
- Hiding stale, pending, failed, dirty, or unresolved finding state from status output.
- Changing review adapter behavior or finding identity generation.
