## ADDED Requirements

### Requirement: Run command SHALL require an active session before startup

`review-gauntlet run` SHALL verify that an active review session exists before loading run adapter configuration, constructing or executing the run controller, or starting the TUI. When no active session exists, it SHALL fail through the same actionable no-active-session diagnostic used by other session-scoped commands.

#### Scenario: Run without init stops before TUI startup

**Given**: a repository root with no `.review-gauntlet/active-session.json`
**When**: the developer runs `review-gauntlet run`
**Then**: the command exits with code `1`
**And**: stderr contains `no active review session; run review-gauntlet init`
**And**: the run TUI is not created or rendered
**And**: no `session_disappeared` run result is emitted

#### Scenario: Missing config does not mask missing session

**Given**: a repository root with no active review session
**And**: no usable run adapter configuration is available
**When**: the developer runs `review-gauntlet run`
**Then**: the command reports `no active review session; run review-gauntlet init`
**And**: it does not report a command adapter configuration error before the session preflight succeeds

#### Scenario: Initialized run behavior remains unchanged

**Given**: a repository root with an active review session
**When**: the developer runs `review-gauntlet run`
**Then**: the command may load adapter configuration, construct the run controller, and use the TUI according to the existing run options
**And**: existing controller outcomes for ready tasks, blocked sessions, finalization, interrupts, and adapter errors remain governed by the existing run-controller behavior
