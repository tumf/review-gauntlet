## ADDED Requirements

### Requirement: Run agent failures SHALL display distinct failure reasons

`review-gauntlet run` SHALL preserve and display distinct external-agent and orchestration failure reasons instead of collapsing them into misleading timeout or generic failure labels. Timeout wording SHALL be reserved for actual timeout failures, and configured timeout details SHALL be rendered concisely without duplicated or unset wording.

#### Scenario: Timeout failure remains distinct

**Given**: a configured command adapter times out during `review-gauntlet run`
**When**: the run result or TUI is rendered
**Then**: the agent status is displayed as timed out
**And**: the display includes the effective timeout duration when available
**And**: the display does not include duplicated wording such as `timeout timeout`

#### Scenario: Command non-zero exit is not displayed as timeout

**Given**: a configured command adapter exits non-zero without timing out
**When**: the run result or TUI is rendered
**Then**: the agent status is displayed as command failed or equivalent non-timeout failure wording
**And**: the display does not label the failure as timed out
**And**: stdout or stderr tail evidence remains available for diagnosis

#### Scenario: Startup error is displayed separately

**Given**: a configured command adapter command cannot be started because the executable is missing
**When**: the run result or TUI is rendered
**Then**: the agent status is displayed as startup error or equivalent wording
**And**: the display does not label the failure as timed out or command non-zero exit

#### Scenario: Template error is displayed separately

**Given**: a configured command adapter has an invalid template or cwd expansion
**When**: `review-gauntlet run` prepares the command adapter step
**Then**: the run result reports a template or configuration error
**And**: no external adapter command is executed
**And**: the TUI does not label the failure as timed out

#### Scenario: Interrupted run is displayed separately

**Given**: a run is interrupted by the user or controller
**When**: the run result or TUI is rendered
**Then**: the status is displayed as interrupted
**And**: the display does not label the interruption as failed command execution or timeout

#### Scenario: Max steps exhaustion is displayed separately

**Given**: `review-gauntlet run` reaches its configured maximum number of ready-prompt executions while the active session remains unfinished
**When**: the run result or TUI is rendered
**Then**: the status is displayed as max steps exhausted or equivalent orchestration wording
**And**: the display does not label the condition as an agent timeout

#### Scenario: Ready-to-finalize timeout recovery remains visible

**Given**: an external command adapter times out while the active session has `can_finalize=true` and no finalize blockers
**When**: the run TUI renders the finalize checklist
**Then**: the TUI preserves the manual-finalize recovery cue
**And**: the timeout remains visible as the agent lifecycle reason
**And**: coverage, finding triage, fix verification, and final checks are not shown as failed solely because the adapter timed out
