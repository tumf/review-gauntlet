## ADDED Requirements

### Requirement: Run controller SHALL include next_required_action in step_started events

`RunController.run()` SHALL include the `next_required_action` string in every `step_started` event payload alongside the existing `step` and `prompt` fields. The `next_required_action` value SHALL come from the same readiness context that produced the ready prompt, ensuring the TUI can classify the step without parsing prompt text. The ready-prompt callable SHALL return both the prompt text and the `next_required_action` as a single structured object so the two values cannot drift.

<!-- Expected canonical result after archive: the canonical run-controller spec will require step_started events to carry next_required_action and the ready-prompt callable to return a structured object containing both prompt and action. -->

#### Scenario: step_started event carries next_required_action

**Given**: a `RunController` with an active session and a ready task
**When**: `RunController.run()` emits a `step_started` event
**Then**: the event payload contains `step`, `prompt`, and `next_required_action` keys
**And**: `next_required_action` is a non-empty string matching the status-derived action for the current session state

#### Scenario: Ready-prompt callable returns structured ReadyTask

**Given**: a `RunController` constructed with a ready-prompt callable
**When**: the controller calls the callable during `run()` or `snapshot()`
**Then**: the callable returns a `ReadyTask` (or equivalent structured object) containing both `prompt` and `next_required_action`
**And**: both fields are derived from the same readiness context
