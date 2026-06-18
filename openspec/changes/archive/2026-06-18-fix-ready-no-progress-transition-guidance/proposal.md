---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/findings.py
  - tests/test_cli_run.py
  - tests/test_run_controller.py
---

# Fix ready no-progress transition guidance

**Change Type**: implementation

## Problem / Context

`review-gauntlet run` can stop at a READY / `no_progress` state when an external resolution agent writes a successful `finish` verdict but the active session state does not change. A recent run showed this happening because the ready prompt told the agent to mark findings as `false_positive`, `accepted_risk`, `waived`, or similar states even though current `open` findings may only transition to `confirmed` or `dismissed` under the existing state machine.

This conflicts with the constitution's requirements that unknown and open states remain visible, findings are stateful, and finding resolution records whether each open finding was confirmed or dismissed.

## Proposed Solution

Align the resolve-phase ready prompt, turn verdict validation feedback, and run-controller no-progress diagnostics with the existing finding transition rules.

- Resolve prompts for open findings will explicitly state the allowed target states for each listed finding.
- Open finding prompts will instruct agents to use `dismissed` with a durable reason for false positives and non-issues, rather than invalid direct transitions such as `false_positive`.
- Invalid transition feedback will be surfaced in a way that helps the next agent turn correct the verdict instead of silently appearing as no progress.
- `no_progress` results will identify that a successful progress verdict did not change targeted state and preserve enough artifact context to diagnose why.

## Acceptance Criteria

- A ready prompt for resolving open findings clearly lists `confirmed` and `dismissed` as the valid transitions for those findings.
- The resolve workflow text no longer suggests states that are invalid for the current ready finding set.
- A turn verdict that attempts an invalid finding transition produces an actionable diagnostic naming the finding ID and attempted transition.
- `review-gauntlet run` does not repeatedly execute the same ready task after a successful-looking verdict that failed to change targeted state.
- Existing valid `dismissed` and `confirmed` resolution flows continue to update findings and allow finalization once coverage and findings are closed.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` builds resolve ready prompts from active finding state and allowed transition metadata rather than a static all-state list.
- `src/review_gauntlet/cli.py` validation paths report invalid resolution transitions with finding ID, current state, and requested state.
- `src/review_gauntlet/run_controller.py` preserves `no_progress` failure behavior while making the returned failure and/or lifecycle artifact context actionable for invalid or no-op verdicts.
- Tests cover prompt guidance, invalid transition diagnostics, no-progress detection, and valid open finding resolution.
- `make check` passes.

## Out of Scope

- Changing the underlying finding state machine to allow `open -> false_positive`, `open -> accepted_risk`, or `open -> waived`.
- Redesigning the full review lifecycle or adding new terminal finding states.
- Implementing automatic source-code fixes beyond the existing resolve workflow.
