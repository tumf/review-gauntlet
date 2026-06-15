---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/run_controller.py
  - tests/test_run_tui.py
  - tests/test_run_controller.py
  - openspec/specs/review-sessions/spec.md
---

# Run TUI coverage dashboard

**Change Type**: implementation

## Problem / Context

`review-gauntlet run` currently launches a Textual presentation that is visually dominated by generic app chrome and low-density static text panels. The first thing users need during an interactive run is not the application name; it is whether the session is moving, how much of the current target is complete, how long it has taken, what remains, and whether the agent is actively running.

The current TUI also renders coverage and findings as plain key/value lists, includes the default Textual header/footer chrome, and does not clearly animate agent activity. In addition, the current run snapshot reads `status["findings"]`, while the status command exposes finding counts as `finding_state_counts`, so the TUI can miss actionable finding-state data.

## Proposed Solution

Replace the current `run` Textual presentation with a compact progress-first dashboard that:

- makes total current-target progress the top visual priority;
- shows percent complete, completed/total current cells, elapsed time, step number, and agent status in one dense header area;
- visualizes coverage composition with compact bars and emphasized remaining states;
- visualizes actionable finding counts as badges or compact state chips;
- animates visible activity while the session-level agent command is running;
- removes default Textual header/footer chrome that emits the meaningless `RunApp` title and left-side icon;
- preserves the existing run controller semantics, run results, TUI eligibility rules, fallback behavior, and keyboard controls.

## Acceptance Criteria

- Interactive text `review-gauntlet run` shows a progress-first TUI whose first visible content includes percent complete, completed/total current cells, elapsed time, current step, and agent status.
- The progress percent is derived deterministically from effective coverage: `pending` and `stale` are incomplete; current target cells in other states are complete; `superseded` cells are shown separately and excluded from the progress denominator.
- Coverage state breakdown is rendered as compact visual bars or equivalent high-density graphical text, with pending and stale states emphasized rather than hidden.
- Finding state counts are shown from the same status data exposed by `review-gauntlet status`, including `finding_state_counts` when no legacy `findings` key exists.
- Agent activity visibly animates or pulses while `RunSnapshot.agent_status == "running"` and becomes non-animated/dim when idle.
- The default Textual header/footer chrome is removed, so the TUI does not display the generic `RunApp` title or default left-side icon.
- TUI-only presentation changes do not alter task selection, command execution, run result JSON/text semantics, active-session finalization, or fallback behavior when optional TUI dependencies are absent.

## Explicit Completion Conditions

- `src/review_gauntlet/run_tui.py` renders a progress-first dashboard without importing or yielding Textual `Header` or `Footer` widgets.
- `src/review_gauntlet/run_controller.py` maps snapshot findings from `finding_state_counts` when that is the status payload key.
- Unit tests cover progress metric calculation, elapsed-time formatting, finding-count fallback, and absence of default header/footer chrome in the TUI implementation.
- Headless TUI execution tests continue to prove the TUI drives `RunController.run()` and returns the controller result.
- `make check` passes.

## Out of Scope

- Reading or displaying host OS CPU utilization.
- Changing the non-TUI `run` output format.
- Changing session task priority, ready prompt selection, coverage state transitions, finding state transitions, or finalization rules.
- Adding new required runtime dependencies beyond the existing optional `tui` extras.
