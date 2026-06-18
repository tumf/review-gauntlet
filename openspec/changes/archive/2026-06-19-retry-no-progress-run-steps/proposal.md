---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_controller.py
  - tests/test_run_controller.py
  - openspec/specs/review-sessions/spec.md
---

# Retry no-progress run steps with actionable diagnostics

**Change Type**: implementation

## Premise / Context

- `review-gauntlet run` currently detects a continuation verdict of `continue` or `finish` that does not change targeted cell/finding state and converts the step into a `no_progress` failure.
- The current behavior stops the autonomous run immediately, leaving the user to manually inspect `ready`, status, findings, and previous turn context.
- The desired behavior is to treat no-progress as an agent-correctable workflow error: point out the missing state transition, retry the same ready task, and keep incompleteness visible.
- The project constitution requires unknown/incomplete state to stay visible and deterministic state transitions to be authoritative rather than inferred from LLM self-report.

## Problem

When an external agent writes a valid turn verdict claiming completion but fails to perform the required repository/session state mutation, `review-gauntlet run` stops with `reason: no_progress`. This is safe but inefficient: the orchestrator has enough information to tell the agent what went wrong and ask it to retry the same scoped task, just as it already does for invalid turn verdict JSON.

## Proposed Solution

Change the run controller so `no_progress` failures schedule a bounded retry when remaining `max_steps` allow it. The retry prompt SHALL preserve the original ready task and append a diagnostic section explaining that the previous turn verdict was syntactically valid but did not change any targeted state.

The diagnostic SHALL include the affected target IDs, task key or verdict path when available, the previous verdict value, and artifact pointers when available. It SHALL instruct the agent to perform the required concrete action (`mark`, review state transition, finalize action, or other ready-task mutation) before writing another finish/continue verdict.

The retry behavior SHALL remain bounded by `--max-steps`; repeated no-progress turns SHALL eventually return a structured `no_progress` result instead of looping forever.

## Acceptance Criteria

- A no-progress turn with remaining step budget schedules a retry of the same ready task instead of stopping immediately.
- The retry prompt clearly explains that the prior turn verdict did not mutate targeted session state and lists the target IDs involved.
- The run emits retry metadata/events that distinguish no-progress retries from invalid-verdict retries.
- Repeated no-progress turns are bounded by `--max-steps` and return a structured `reason: no_progress` result when the retry budget is exhausted.
- Existing invalid-verdict retry behavior remains unchanged.
- The implementation preserves constitution principles: no state is marked complete from LLM self-report alone, and open/incomplete state remains visible.

## Explicit Completion Conditions

- `src/review_gauntlet/run_controller.py` retries `reason == "no_progress"` with a dedicated diagnostic prompt when `step_number < max_steps`.
- `tests/test_run_controller.py` contains regression coverage proving first no-progress retries, second no-progress with exhausted steps stops, and invalid verdict retry behavior still works.
- Focused tests for the run controller pass with `uv run pytest tests/test_run_controller.py`.
- Project checks pass with `make check`.

## Out of Scope

- Changing `review-gauntlet review` semantics.
- Marking findings or cells as progressed based only on a turn verdict.
- Adding unbounded retries or retry counters outside the existing `--max-steps` limit.
- Changing TUI layout beyond rendering existing structured run-step/failure state.
