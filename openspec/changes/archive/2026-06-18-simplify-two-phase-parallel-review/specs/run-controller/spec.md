## MODIFIED Requirements

### Requirement: Run controller SHALL record finalized agent status on session disappearance

When `RunController.run()` detects that the active session file no longer exists after a phase step, the controller SHALL set its internal agent status to `"finalized"` and produce a terminal lifecycle before returning a completed result.

`RunController.snapshot()` SHALL tolerate transient operating-system errors and database-layer errors from readiness or status computation, including `OSError` from subprocess-backed git commands and `sqlite3.Error` from ledger access. When readiness cannot be computed due to resource exhaustion or database unavailability, the snapshot SHALL be produced with `next_ready_prompt` set to `None` and SHALL NOT crash the TUI or the calling code.

#### Scenario: Snapshot reflects finalized state after agent finalizes session

**Given**: an active review session whose agent step removes the active session file
**When**: `RunController.run()` completes via the finalize-success branch
**Then**: `controller.snapshot().agent_status == "finalized"`
**And**: the snapshot's lifecycle status is not `"running"`

#### Scenario: TUI finalize checkpoint gate renders done complete

**Given**: a `RunSnapshot` with `agent_status == "finalized"` and `session_state is None`
**When**: `derive_finalize_gates(snapshot)` builds the finalize path
**Then**: the sixth gate has state `"done"` and detail `"complete"`
**And**: the header state class is `panel-finalized`

#### Scenario: Non-finalize completions do not falsely report finalized status

**Given**: a `RunController` whose command fails, is interrupted, or exhausts max steps while the active session remains
**When**: the run returns a non-completed or blocked result
**Then**: the controller's agent status is never `"finalized"`

## ADDED Requirements

### Requirement: Run controller SHALL support two-phase execution

`RunController.run()` SHALL execute the review session in two phases: Phase 1 (review all pending cells) and Phase 2 (resolve all open findings). Phase 2 SHALL NOT begin until Phase 1 succeeds with no remaining pending cells. Each phase SHALL consume one step count. The TUI SHALL display the current phase.

#### Scenario: Run executes Phase 1 then Phase 2

**Given**: an active session with pending cells
**When**: `review-gauntlet run` starts
**Then**: Phase 1 reviews all pending cells in parallel
**And**: Phase 2 begins after all cells are reviewed
**And**: the TUI displays the current phase

#### Scenario: Run stops after Phase 1 if Phase 1 fails

**Given**: an active session with pending cells
**And**: at least one review adapter invocation fails irrecoverably
**When**: `review-gauntlet run` executes Phase 1
**Then**: Phase 2 does not start
**And**: the TUI displays the failure reason

#### Scenario: Phase 2 consumes steps per continuation round

**Given**: an active session with open findings on 2 files
**And**: one file requires 2 continuation rounds to finish
**When**: `review-gauntlet run --max-steps 3` runs
**Then**: Phase 1 consumes 1 step
**And**: Phase 2 round 1 (both files) consumes 1 step
**And**: Phase 2 round 2 (continuing file) consumes 1 step
**And**: run completes successfully

### Requirement: Resolve command SHALL require an active session before startup

`review-gauntlet resolve` SHALL verify that an active review session exists before loading adapter configuration or executing resolution agents. When no active session exists, it SHALL fail through the same actionable no-active-session diagnostic used by other session-scoped commands.

#### Scenario: Resolve without init stops before agent startup

**Given**: a repository root with no `.review-gauntlet/active-session.json`
**When**: the developer runs `review-gauntlet resolve`
**Then**: the command exits with code `1`
**And**: stderr contains `no active review session; run review-gauntlet init`
