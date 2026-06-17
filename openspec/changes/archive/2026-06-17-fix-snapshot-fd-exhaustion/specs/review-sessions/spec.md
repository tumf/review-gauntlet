## MODIFIED Requirements

### Requirement: Finalize SHALL validate completion without running review work

`status` and `finalize` SHALL tolerate malformed persisted finding-event metadata without crashing. Malformed terminal-decision metadata SHALL be surfaced conservatively as a blocker so completion cannot hide invalid waiver or accepted-risk state.

`status`, `run` readiness, and `finalize` SHALL tolerate subprocess startup `OSError` from git-based cleanliness checks and `sqlite3.Error` from ledger database access without printing a raw traceback as the final user-facing result. If review-universe cleanliness, non-review dirty state, or target digest freshness cannot be verified because a git subprocess cannot start or the ledger database is unavailable, the command SHALL surface a conservative blocker and SHALL NOT claim finalization readiness.

#### Scenario: Ledger database unavailability blocks status finalization readiness

**Given**: an active review session that otherwise may be close to finalizable
**And**: `sqlite3.connect` against the session ledger raises `sqlite3.OperationalError` (e.g., due to file descriptor exhaustion or database lock)
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON
**And**: `finalize_blockers` includes a blocker indicating the ledger database access is unavailable
**And**: `can_finalize` is `false`
**And**: no raw traceback is printed as the final user-facing result

#### Scenario: Ledger database unavailability blocks run readiness without TUI crash

**Given**: a running TUI session with an active review session
**And**: TUI refresh triggers `_ready_prompt` computation that raises `sqlite3.OperationalError`
**When**: the TUI timer calls `RunController.snapshot()`
**Then**: the snapshot is produced with `next_ready_prompt` set to `None`
**And**: the TUI remains responsive without a fatal worker-thread crash
**And**: the finalize checklist shows the blocked status
