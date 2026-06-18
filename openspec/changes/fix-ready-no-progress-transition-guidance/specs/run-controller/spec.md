## ADDED Requirements

### Requirement: Run controller SHALL stop no-op successful verdict loops with actionable context

`RunController.run()` SHALL compare targeted session state before and after a successful progress verdict. If the verdict reports progress but the targeted state is unchanged, the controller SHALL stop the run with `reason: no_progress` instead of re-running the same ready task indefinitely. The returned failure metadata SHALL identify the task key, targeted IDs when known, and the artifact path or equivalent run evidence needed to inspect the no-op verdict.

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
