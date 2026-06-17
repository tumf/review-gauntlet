---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
  - openspec/specs/review-sessions/spec.md
---

# Add run TUI value flash highlights

**Change Type**: implementation

## Premise / Context

- `review-gauntlet run` renders an interactive Textual TUI from `src/review_gauntlet/run_tui.py` when text output is selected and stdout is a TTY.
- The current TUI refresh loop updates whole `Static` widgets on a 0.25 second interval, but it does not distinguish meaningful data changes from natural time-based refreshes.
- The requested behavior is visual-only: highlight the smallest changed displayed value, not the whole row or panel.
- Auto-updating time counters such as quiet duration, last-output age, timeout countdown, elapsed time, and spinner frames must not trigger flash highlights.

## Problem / Context

The run TUI makes review-session progress visible, but changes can be easy to miss because refreshed values replace prior values without any visual cue. A panel-wide flash would overstate the scope of a change and create visual noise, especially while the TUI updates frequently. Time-based counters also change naturally and would cause distracting constant flashing if treated as meaningful updates.

## Proposed Solution

Add value-level flash highlighting to the run TUI render path. The TUI should track stable, semantic display fields across refreshes and temporarily mark only fields whose non-volatile values changed since the previous render. The implementation should keep the current non-TUI text helpers stable and introduce TUI-specific rich rendering, widget partitioning, or an equivalent mechanism that can style only changed values.

The change should use stable comparison keys that exclude volatile time counters. For example, `quiet 7s` and `quiet 8s` should compare as the same liveness kind, while `running` to `quiet` should compare as a meaningful state transition.

## Acceptance Criteria

- The run TUI flash-highlights changed values at the smallest practical displayed value boundary rather than highlighting an entire panel.
- Coverage changes highlight only the changed coverage value(s); for example, `0 / 2` to `1 / 2` highlights the changed completed value, not the whole Session panel.
- Agent-step changes highlight only the changed step value; for example, `Agent step 1` to `Agent step 2` highlights `2`, not the whole row or panel.
- Finding-count changes highlight only the changed count or compact count fragment.
- Finalize checklist changes highlight only the changed gate field or detail fragment instead of the entire checklist panel.
- Activity timeline updates may highlight newly added event/output lines, but timestamp-only changes do not flash.
- Natural time changes in `quiet Ns`, `last output Ns ago`, `timeout in Ns`, elapsed time, and spinner frames do not trigger flash highlights.
- Meaningful state-kind transitions still flash, including `running` to `quiet` and `timeout not configured` to `timeout in ...`.
- JSON output, `--no-tui`, non-TUI text output, run controller behavior, session state, finding state, and finalization behavior remain unchanged.

## Explicit Completion Conditions

- `src/review_gauntlet/run_tui.py` contains a TUI render path or helper layer that can apply flash styling at field/value granularity.
- The TUI comparison state uses stable semantic keys that ignore volatile time-only values.
- Existing plain-text helper outputs such as `session_summary_text()`, `agent_summary_text()`, `finalize_path_text()`, `activity_text()`, and `header_text()` remain suitable for non-TUI rendering and existing tests.
- `tests/test_run_tui.py` includes regression coverage for value-level highlighting, panel/row over-highlighting avoidance, and volatile time-counter exclusion.
- Focused TUI tests pass with `uv run pytest tests/test_run_tui.py`.
- CLI output selection tests covering JSON and TUI-disabled paths continue to pass.

## Out of Scope

- Changing run-controller snapshot semantics or persisted session state.
- Changing non-TUI text or JSON output formats.
- Adding a CLI flag for highlight behavior.
- Implementing a full diff viewer or character-by-character arbitrary text diff.
- Reworking the entire TUI layout beyond what is needed for value-level flash rendering.
