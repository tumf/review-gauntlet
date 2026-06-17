---
change_type: implementation
priority: medium
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - tests/test_run_tui.py
---

# Add actionable coverage overview to the run TUI

**Change Type**: implementation

## Premise / Context

- `review-gauntlet` treats coverage as a first-class product output and must keep pending, stale, failed, and needs-retry states visible.
- The durable coverage model is file × rule review cells, but showing the full matrix in the run TUI overview does not scale with terminal dimensions.
- The current run TUI renders header, finalize checklist, Agent, Session, and Activity panels from aggregate coverage and finding counts.
- The desired btop-like overview is not a wide matrix; it is an actionable dashboard that compresses large state into summary metrics, prioritized work, hot spots, findings, and activity.
- Detailed matrix-like navigation should move to focused file/rule/cell views rather than occupying the overview.

## Problem / Context

The run TUI currently communicates aggregate coverage and finalization progress, but it does not show the developer which review cell should be handled next or which file/rule combinations are making finalization risky. A naive coverage matrix would expose the internal model too directly and quickly become unusable as file and rule counts grow.

The overview needs to answer the operational question: what is blocking finalization, and what should be reviewed next?

## Proposed Solution

Introduce an actionable coverage display model for `review-gauntlet run` TUI:

- Treat the full file × rule matrix as internal session data.
- Add deterministic projections derived from current review cells and findings:
  - prioritized next review queue
  - rule coverage summary
  - file hotlist
  - open finding summary/list
  - recent activity
- Keep the overview focused on these projections instead of rendering the complete matrix.
- Add focused drill-down views for files, rules, cells, findings, and agent details.
- Provide responsive layouts so narrow terminals prioritize status, blockers, queue, and activity.
- Preserve existing JSON/text output behavior unless an explicit future command adds these projections to non-TUI output.

## Acceptance Criteria

- The run TUI overview does not render a complete file × rule coverage matrix.
- The overview displays a prioritized next review queue derived from concrete current review cells and actionable findings.
- Queue priorities are deterministic and expose P0/P1/P2/P3 labels rather than raw scores.
- The overview displays rule-level aggregate coverage and file-level hotlist projections when terminal width permits.
- Narrow terminal layouts remain useful by prioritizing session status, coverage summary, finalize blockers, queue, and activity.
- File, rule, and cell detail views provide focused matrix-like navigation without making the overview wide.
- Existing finalization gates, coverage/finding state semantics, and non-TUI output behavior remain unchanged.

## Explicit Completion Conditions

This change is complete when repository evidence shows:

- TUI state construction derives actionable coverage projections from the same current-cell freshness rules used by readiness/status computation.
- `RunSnapshot` or an equivalent TUI-facing model carries enough typed state to render queue/rule/file/finding projections without reparsing display strings.
- `src/review_gauntlet/run_tui.py` renders overview and drill-down views with stable keybindings while preserving existing interrupt, refresh, and stop behavior.
- `tests/test_run_tui.py` or new focused tests verify priority ordering, aggregate projections, responsive overview fallback, and absence of full matrix rendering in overview.
- Existing CLI behavior remains validated by the project check command.

## Out of Scope

- Changing the underlying review-cell identity model.
- Replacing markdown report matrix output.
- Adding mouse-driven TUI interactions.
- Persisting new ledger tables solely for display projections unless implementation proves derived computation is insufficient.
- Implementing external orchestration or auto-looping behavior.
