## MODIFIED Requirements

### Requirement: Run controller SHALL record finalized agent status on session disappearance

When `RunController.run()` detects that the active session file no longer exists after an agent step, the controller SHALL set its internal agent status to `"finalized"` and produce a terminal lifecycle before returning a completed result.

`RunController.snapshot()` SHALL tolerate transient operating-system errors and database-layer errors from readiness or status computation, including `OSError` from subprocess-backed git commands and `sqlite3.Error` from ledger access. When readiness cannot be computed due to resource exhaustion or database unavailability, the snapshot SHALL be produced with `next_ready_prompt` set to `None` and SHALL NOT crash the TUI or the calling code.

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
