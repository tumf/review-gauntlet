## MODIFIED Requirements

### Requirement: Run controller SHALL record finalized agent status on session disappearance

When `RunController.run()` detects that the active session file no longer exists after an agent step, the controller SHALL set its internal agent status to `"finalized"` and produce a terminal lifecycle before returning a completed result.

`RunController.snapshot()` SHALL tolerate transient operating-system errors from readiness or status computation, including `OSError` from subprocess-backed git commands. When readiness cannot be computed due to resource exhaustion, the snapshot SHALL be produced with `next_ready_prompt` set to `None` and SHALL NOT crash the TUI or the calling code.

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
