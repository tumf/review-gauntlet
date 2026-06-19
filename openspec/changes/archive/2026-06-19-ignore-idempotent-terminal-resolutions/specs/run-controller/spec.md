## MODIFIED Requirements

### Requirement: Run controller SHALL stop no-op successful verdict loops with actionable context

`RunController.run()` SHALL compare targeted session state before and after a successful progress verdict. If the verdict reports progress but the targeted state is unchanged, the controller SHALL stop the run with `reason: no_progress` instead of re-running the same ready task indefinitely. The returned failure metadata SHALL identify the task key, targeted IDs when known, and the artifact path or equivalent run evidence needed to inspect the no-op verdict.

Ignored idempotent terminal resolutions SHALL NOT count as targeted state progress. When a successful-looking verdict contains only stale/idempotent terminal no-op resolutions for the current ready task, the run controller SHALL treat the step as no progress and include enough ignored-resolution or artifact context for a developer to diagnose stale verdict output.

#### Scenario: Successful-looking verdict with unchanged target state stops as no progress

**Given**: an active session with an open finding targeted by the current ready task
**And**: the external agent writes a syntactically successful `finish` verdict
**And**: applying the verdict leaves the targeted finding state unchanged
**When**: `RunController.run()` compares the pre-step and post-step targeted state
**Then**: the run returns `completed: false`
**And**: the result reason is `no_progress`
**And**: the failure metadata identifies the targeted finding ID or task key
**And**: the controller does not immediately execute the same ready task again

#### Scenario: No-progress context points to preserved verdict evidence

**Given**: a run step writes a verdict artifact that does not change targeted state
**When**: the controller reports `no_progress`
**Then**: the lifecycle or failure context includes the run artifact path or equivalent evidence location
**And**: a developer can inspect the preserved artifact to diagnose the no-op verdict

#### Scenario: Stale-only terminal resolutions stop as no progress

**Given**: an active session whose current ready task targets finding `RGF-2001`
**And**: `RGF-2001` is already in a terminal state before the step result is reconciled
**And**: the external agent writes a syntactically successful `finish` verdict requesting the same terminal state for `RGF-2001`
**When**: `RunController.run()` reconciles the verdict and compares targeted state before and after the step
**Then**: the ignored idempotent resolution does not count as progress
**And**: the run returns `completed: false` with `reason: no_progress`
**And**: the failure metadata or lifecycle context identifies `RGF-2001`, the task key or verdict artifact path, and that the resolution was ignored as stale/idempotent
**And**: the controller does not immediately execute the same ready task again
