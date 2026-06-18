## MODIFIED Requirements

### Requirement: Run agent failures SHALL display distinct failure reasons

`review-gauntlet run` SHALL preserve and display distinct external-agent and orchestration failure reasons instead of collapsing them into misleading timeout or generic failure labels. Timeout wording SHALL be reserved for actual timeout failures, and configured timeout details SHALL be rendered concisely without duplicated or unset wording.

Quiet timeout caused by lack of stdout/stderr output SHALL remain distinguishable from overall wall-clock command timeout in structured run results and artifacts, while human-facing terminal TUI wording MAY present both as timeout-family failures.

When a continuation-aware run step writes a syntactically valid `continue` or `finish` turn verdict but the targeted review cell or finding state is unchanged, `review-gauntlet run` SHALL treat the turn as `no_progress`. If remaining `--max-steps` budget exists, the controller SHALL retry the same ready task with an appended diagnostic prompt that explains the missing state change and identifies the affected target IDs. If no retry budget remains, the controller SHALL stop with a structured `no_progress` failure that preserves the target IDs, verdict path or task key, previous verdict value, and available command artifacts.

<!-- Expected canonical result after archive: run failure semantics distinguish `quiet_timeout`, `timeout`, invalid verdicts, and no-progress turns; no-progress turns retry with diagnostics while bounded by max steps. -->

#### Scenario: No-progress turn retries with actionable diagnostic

**Given**: an active session has a ready task targeting finding `RGF-0001`
**And**: the external agent writes a valid continuation verdict with `verdict: finish`
**And**: finding `RGF-0001` remains in the same state after the turn
**And**: `review-gauntlet run` has remaining `--max-steps` budget
**When**: the run controller evaluates the completed turn
**Then**: the step is recorded with `reason: no_progress`
**And**: the controller schedules the same ready task for retry
**And**: the retry prompt includes a no-progress diagnostic naming `RGF-0001`
**And**: the retry prompt tells the agent to perform the required state-changing action before writing another verdict

#### Scenario: Repeated no-progress remains bounded

**Given**: an active session has a ready task targeting finding `RGF-0001`
**And**: every attempted turn writes a valid continuation verdict without changing finding `RGF-0001`
**When**: `review-gauntlet run` reaches its configured `--max-steps` limit
**Then**: the run stops with `completed: false`
**And**: the run result reports `reason: no_progress`
**And**: the final failure payload preserves target IDs and verdict diagnostics

#### Scenario: Invalid verdict retry remains separate from no-progress retry

**Given**: an active session has a ready task
**When**: a run step writes an invalid turn verdict payload
**Then**: the retry diagnostic is labelled as an invalid verdict diagnostic
**And**: the failure reason remains `invalid_step_verdict`
**And**: the no-progress diagnostic is not used for that retry
