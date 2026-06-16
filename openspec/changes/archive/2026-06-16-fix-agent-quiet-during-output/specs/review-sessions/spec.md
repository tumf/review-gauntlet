## ADDED Requirements

### Requirement: Run agent liveness SHALL reflect actual output activity

`review-gauntlet run` SHALL track agent subprocess stdout and stderr output as it is produced, not only after the subprocess exits. The agent liveness status SHALL reflect the time since the most recent output line, not the time since the subprocess was started. An agent that is actively producing output SHALL be displayed as "running", not "quiet". The Activity panel SHALL show live output tail entries during agent execution.

#### Scenario: Agent producing output is shown as running

**Given**: a configured command adapter subprocess is running during `review-gauntlet run`
**And**: the subprocess has produced stdout output within the last 5 seconds
**When**: the TUI refreshes the agent lifecycle snapshot
**Then**: the agent status is displayed as running
**And**: `last_output_age_seconds` reflects the time since the most recent output line
**And**: the Activity panel includes the most recent output lines

#### Scenario: Agent with no recent output is shown as quiet

**Given**: a configured command adapter subprocess is running during `review-gauntlet run`
**And**: the subprocess has not produced any stdout or stderr output for at least 5 seconds
**When**: the TUI refreshes the agent lifecycle snapshot
**Then**: the agent status is displayed as quiet
**And**: `last_output_age_seconds` reflects the time since the last output line or the subprocess start time if no output has been produced

#### Scenario: Output tail is available before process completion

**Given**: a configured command adapter subprocess is running during `review-gauntlet run`
**And**: the subprocess has produced multiple lines of stdout output
**When**: the TUI refreshes the agent lifecycle snapshot before the subprocess exits
**Then**: the agent lifecycle `output_tail` contains the most recent output lines
**And**: the entries are available for Activity panel rendering without waiting for process completion
