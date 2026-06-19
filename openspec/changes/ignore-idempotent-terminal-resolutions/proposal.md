---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/findings.py
  - src/review_gauntlet/continuation.py
  - src/review_gauntlet/run_controller.py
  - tests/test_cli_run.py
  - tests/test_run_controller.py
  - openspec/specs/review-sessions/spec.md
  - openspec/specs/run-controller/spec.md
---

# Ignore Idempotent Terminal Resolutions

**Change Type**: implementation

## Premise / Context

- `review-gauntlet run` validates turn verdict `resolutions` against the active session's current finding states before persistence.
- Current validation correctly rejects invalid transitions, but it also treats stale or duplicate terminal-state resolutions as hard failures.
- A recent failure showed a terminal finding such as `false_positive` being included again in a turn verdict, producing `turn verdict contains invalid finding transition for active session` and causing repeated run interruption.
- The constitution requires findings to remain stateful, session-scoped truth to be explicit, and orchestration loops to halt with clear diagnostics instead of retrying indefinitely.

## Problem / Context

External agents can repeat already-decided findings in continuation verdicts, especially when previous turn context or stale artifacts include IDs that are no longer actionable. When a repeated resolution is idempotent, such as `dismissed -> dismissed` or `false_positive -> false_positive`, rejecting the whole turn as an invalid transition is unnecessarily brittle: no semantic state change is being requested, and valid resolutions in the same verdict may be blocked.

At the same time, review-gauntlet must not silently allow meaningful rewrites of terminal decisions, such as `confirmed -> dismissed` or `false_positive -> dismissed`, because those would alter a recorded human/agent decision without an explicit supported transition.

## Proposed Solution

Adjust turn verdict validation and application so stale/idempotent terminal resolutions are classified separately from invalid state changes.

- Treat resolutions whose requested state exactly matches the current terminal state as stale/idempotent and ignore them without changing ledger state.
- Preserve hard rejection for transitions that would change a terminal finding to a different state.
- Preserve hard rejection for non-terminal invalid transitions such as `open -> false_positive`.
- Surface ignored stale resolutions in structured diagnostics or run metadata so users can see that a verdict referenced already-resolved findings.
- Improve diagnostics when the verdict path/session context differs from the active session being validated, so stale artifacts are easier to identify.

## Acceptance Criteria

- Idempotent resolutions for terminal findings, such as `dismissed -> dismissed` and `false_positive -> false_positive`, do not cause `validate-turn-verdict` or `review-gauntlet run` to fail.
- Meaning-changing terminal transitions, such as `confirmed -> dismissed` or `false_positive -> dismissed`, remain invalid and report the finding ID, current state, requested state, and allowed/terminal context.
- Non-terminal invalid transitions, such as `open -> false_positive`, remain invalid and continue to report allowed target states.
- Ignored stale/idempotent resolutions are visible in structured output, metadata, or preserved artifacts rather than silently disappearing.
- Run-controller no-progress protection remains intact: if a verdict contains only ignored stale resolutions and makes no targeted state progress, the run stops with actionable `no_progress` context rather than looping.
- Diagnostics identify or preserve enough context to distinguish active-session validation from stale verdict/session artifacts.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` distinguishes valid transitions, invalid transitions, and idempotent terminal no-op resolutions during turn verdict validation/application.
- Applying a verdict with mixed valid resolutions and idempotent terminal no-op resolutions persists only the valid state changes and reports/records the ignored no-op resolutions.
- Existing prompt guidance continues to list only state-machine-allowed target states for actionable findings.
- Tests cover idempotent terminal no-op acceptance, terminal semantic-change rejection, non-terminal invalid transition rejection, mixed-verdict behavior, and run-controller no-progress behavior for stale-only verdicts.
- `make check` passes.

## Out of Scope

- Adding new finding states.
- Allowing direct `open -> false_positive`, `open -> accepted_risk`, or `open -> waived` transitions.
- Reopening or changing terminal finding decisions through turn verdicts.
- Changing the external agent prompt contract beyond diagnostics needed to explain stale/no-op resolutions.
