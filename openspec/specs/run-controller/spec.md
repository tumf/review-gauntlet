### Requirement: Run controller SHALL record finalized agent status on session disappearance

When `RunController.run()` detects that the active session file no longer exists after an agent step, the controller SHALL set its internal agent status to `"finalized"` and produce a terminal lifecycle before returning a completed result.

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

#### Scenario: Snapshot tolerates git subprocess resource exhaustion

**Given**: an active review session
**And**: readiness or finalize-blocker computation raises `OSError` with `errno.EMFILE` from a git subprocess
**When**: `RunController.snapshot()` is called during TUI refresh
**Then**: the snapshot is produced without raising an exception
**And**: `next_ready_prompt` is `None`
**And**: finalize blockers include a resource-exhaustion indicator if the failure occurred during finalize-blocker computation
**And**: the TUI continues rendering with the available session status data

#### Scenario: Snapshot tolerates sqlite3 OperationalError from status computation

**Given**: an active review session
**And**: the session ledger file exists but `sqlite3.connect` raises `sqlite3.OperationalError` due to file descriptor exhaustion or database lock
**When**: `RunController.snapshot()` is called during TUI refresh
**Then**: the snapshot is produced without raising an exception
**And**: `next_ready_prompt` is `None`
**And**: finalize blockers include a database-unavailability indicator
**And**: the TUI continues rendering with the available session status data

#### Scenario: Snapshot tolerates sqlite3 OperationalError from readiness computation

**Given**: an active review session
**And**: the `_ready_prompt` callable raises `sqlite3.OperationalError` during finding-count or coverage query
**When**: `RunController.snapshot()` is called during TUI refresh
**Then**: the snapshot is produced without raising an exception
**And**: `next_ready_prompt` is `None`
**And**: the TUI continues rendering without a fatal worker-thread crash

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
