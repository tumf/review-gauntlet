## MODIFIED Requirements

### Requirement: Run controller SHALL record finalized agent status on session disappearance

When `RunController.run()` detects that the active session file no longer exists after a phase step, the controller SHALL set its internal agent status to `"finalized"` and produce a terminal lifecycle before returning a completed result. The controller SHALL preserve the final session snapshot or equivalent final status summary captured before active-session disappearance makes normal status lookup unavailable, so later `RunController.snapshot()` calls after finalization do not replace completed coverage, finding counts, or terminal cell counts with empty fallback values.

`RunController.snapshot()` SHALL tolerate transient operating-system errors and database-layer errors from readiness or status computation, including `OSError` from subprocess-backed git commands and `sqlite3.Error` from ledger access. When readiness cannot be computed due to resource exhaustion or database unavailability, the snapshot SHALL be produced with `next_ready_prompt` set to `None` and SHALL NOT crash the TUI or the calling code.

<!-- Expected canonical result after archive: finalized controller snapshots will retain the last complete coverage/finding summary captured before the active session disappears, preventing finalized UI refreshes from displaying empty progress. -->

#### Scenario: Snapshot reflects finalized state after agent finalizes session

**Given**: an active review session whose agent step removes the active session file
**When**: `RunController.run()` completes via the finalize-success branch
**Then**: `controller.snapshot().agent_status == "finalized"`
**And**: the snapshot's lifecycle status is not `"running"`

#### Scenario: Finalized snapshot preserves completed coverage

**Given**: an active review session with non-zero reviewed cell coverage and terminal finding counts
**And**: an agent step finalizes the session and removes the active session file
**When**: `RunController.run()` returns completed and a later caller asks for `controller.snapshot()`
**Then**: the snapshot still reports the final coverage counts captured before finalization
**And**: `cell_terminal_count` remains the final terminal cell count rather than `0`
**And**: finding counts remain the final finding counts rather than an empty mapping

#### Scenario: TUI finalize checkpoint gate renders done complete

**Given**: a `RunSnapshot` with `agent_status == "finalized"` and `session_state is None`
**When**: `derive_finalize_gates(snapshot)` builds the finalize path
**Then**: the sixth gate has state `"done"` and detail `"complete"`
**And**: the header state class is `panel-finalized`

#### Scenario: Non-finalize completions do not falsely report finalized status

**Given**: a `RunController` whose command fails, is interrupted, or exhausts max steps while the active session remains
**When**: the run returns a non-completed or blocked result
**Then**: the controller's agent status is never `"finalized"`
