---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
  - openspec/specs/review-sessions/spec.md
---

# Remove TUI Quiet Heartbeat Activity Rows

**Change Type**: implementation

## Premise / Context

- The current `review-gauntlet run` TUI synthesizes `agent alive no output for ...` rows in the Activity timeline while an agent is quiet.
- The heartbeat row is frame-gated, so it appears and disappears as `activity_frame` changes, which creates distracting timeline churn.
- Header and Agent summary already expose quiet/liveness state and output recency.
- The canonical `review-sessions` spec currently allows and expects quiet heartbeat rows in Activity, so the implementation and spec must change together.

## Problem / Context

The Activity panel is meant to present stable, useful run activity. A synthetic quiet heartbeat row is currently inserted into the Activity timeline and intentionally hidden on most animation frames. This makes the timeline visually unstable even though no real event or output has occurred.

## Proposed Solution

Stop rendering quiet-running agent heartbeat rows in the Activity timeline. Keep quiet/liveness information in the existing Header and Agent summary fields, and keep Activity focused on normalized Review Gauntlet events plus bounded stdout/stderr output tail rows.

## Acceptance Criteria

- When an active agent is quiet, Activity no longer contains `agent alive no output ...` or equivalent synthetic quiet heartbeat rows.
- Quiet/liveness state remains visible in the Header and Agent summary, including elapsed quiet duration when known.
- Activity continues to render normalized Review Gauntlet event rows and sanitized stdout/stderr rows.
- Removing Activity heartbeat rows does not change task selection, command execution, result payloads, interruption behavior, JSON output behavior, non-TUI behavior, fallback behavior, or session finalization semantics.
- TUI tests cover the absence of quiet heartbeat rows and the continued presence of Header/Agent liveness information.

## Explicit Completion Conditions

- `src/review_gauntlet/run_tui.py` no longer appends quiet heartbeat timeline events to `RunViewState.timeline_events`.
- Any now-unused heartbeat helper is removed or made unreachable without leaving dead code that lint flags.
- `tests/test_run_tui.py` asserts that quiet agents do not add Activity heartbeat rows across animation frames while Header/Agent liveness remains present.
- The canonical spec delta modifies `Status and findings commands SHALL expose actionable session state` to describe stable Activity behavior without quiet heartbeat rows.
- `make check` passes.

## Out of Scope

- Changing non-TUI command behavior or JSON output contracts.
- Removing quiet/liveness labels from the Header or Agent summary.
- Redesigning the Activity panel layout beyond removing quiet heartbeat timeline rows.
