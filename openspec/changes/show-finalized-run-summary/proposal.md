---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/run_tui.py
  - tests/test_run_controller.py
  - tests/test_run_tui.py
  - openspec/specs/run-controller/spec.md
  - openspec/specs/review-sessions/spec.md
---

# Show Finalized Run Summary

**Change Type**: implementation

## Problem/Context

`review-gauntlet run` currently renders live operational panels while a run is active, but after an agent finalizes a session the TUI refresh path can rebuild its snapshot after `.review-gauntlet/active-session.json` has disappeared. That fallback snapshot has empty coverage, empty findings, and `cell_terminal_count=0`, causing the finalized header to appear as if progress returned to `0%`.

At finalized time the operational panels for queue, rule coverage, file hotlist, findings projection, and activity are no longer useful as next-action guidance. The user needs a completion screen that preserves final progress and highlights completed work: resolved files, rules, findings, checkpoint commit, elapsed time, and step count.

## Proposed Solution

Preserve the final run snapshot before active-session teardown makes normal status recomputation unavailable, and switch the finalized TUI from operational review panels to a concise achievement-oriented summary screen.

The implementation will:

- Cache or otherwise preserve final coverage, finding, lifecycle, session, and elapsed fields for `RunController.snapshot()` after `agent_status == "finalized"`.
- Keep finalized coverage and findings visible instead of falling back to empty status data.
- Add a finalized summary model/render path in `src/review_gauntlet/run_tui.py` that surfaces final coverage, terminal cell counts, resolved finding counts, resolved files, rule IDs, finding IDs, elapsed time, run step count, and checkpoint commit metadata when available.
- Hide the queue, rule coverage, file hotlist, findings projection, and activity panels while finalized summary is displayed.
- Preserve non-finalized TUI behavior and non-TUI output semantics.

## Acceptance Criteria

- After `review-gauntlet run` reaches finalized status, the interactive TUI does not display `0%` merely because the active session file has been removed.
- The finalized header displays the final coverage percentage and reviewed/total cell counts captured before finalization.
- The finalized screen displays a work summary including elapsed time, run steps, checkpoint commit short SHA or clear commit-unavailable reason, resolved finding count, resolved files, and associated rule/finding identifiers.
- The queue, rule coverage, file hotlist, findings projection, and activity panels are not rendered as active operational panels in the finalized screen.
- Empty summary categories render explicit zero/none wording instead of disappearing silently or inventing work.
- Running/blocked/failed/non-finalized TUI states keep their current operational panels and navigation behavior.
- JSON/text non-TUI run result behavior remains compatible except for any additional summary metadata that may be added without removing existing keys.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `RunController` preserves the final non-empty snapshot or equivalent final session summary before finalized active-session disappearance can erase coverage and finding data.
- `src/review_gauntlet/run_tui.py` contains a finalized summary render path that displays statistical/completion-oriented information rather than operational next-action panels.
- `tests/test_run_controller.py` or an equivalent controller-level test proves finalized snapshots retain final coverage and `cell_terminal_count` after the active session file is removed.
- `tests/test_run_tui.py` proves finalized render sections and/or dashboard state preserve final coverage and include commit/elapsed/finding/file/rule summary fields.
- A regression test proves finalized rendering hides queue/rules/files/findings/activity operational content while preserving normal non-finalized rendering.
- `make check` passes.
- `cflx openspec validate show-finalized-run-summary --strict` passes.

## Out of Scope

- Changing review/finding state transition semantics.
- Changing checkpoint commit behavior or git commit creation policy.
- Adding historical report persistence beyond the final in-memory run/TUI summary needed for the finalized screen.
- Changing non-TUI markdown report generation.
- Reworking Textual navigation for non-finalized drill-down views.
