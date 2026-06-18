## ADDED Requirements

### Requirement: Run TUI SHALL throttle expensive automatic status snapshots

`review-gauntlet run` TUI SHALL decouple high-frequency visual refresh from expensive session status recomputation. Automatic background refresh SHALL NOT call `RunController.snapshot()` on every visual tick when the previous full snapshot is still within the configured freshness window. The TUI SHALL continue to show liveness from the cached snapshot between full refreshes.

<!-- Expected canonical result after archive: the run-controller spec will require the run TUI to rate-limit automatic full snapshots so repository status recomputation cannot saturate CPU during long-running agent steps. -->

#### Scenario: Automatic refresh reuses fresh snapshot

**Given**: a run TUI with an active agent step
**And**: the TUI already has a full snapshot whose age is inside the automatic refresh freshness window
**When**: the automatic background refresh timer fires repeatedly
**Then**: the TUI reuses the cached snapshot for those ticks
**And**: it does not call `RunController.snapshot()` once per timer tick
**And**: it may continue updating liveness-only display state

#### Scenario: Automatic refresh obtains a new snapshot after throttle expiry

**Given**: a run TUI with an active agent step
**And**: the cached full snapshot is older than the automatic refresh freshness window
**When**: the automatic background refresh timer fires
**Then**: the TUI calls `RunController.snapshot()` once to refresh full session state
**And**: subsequent automatic ticks inside the new freshness window reuse that snapshot

#### Scenario: Manual refresh bypasses throttle

**Given**: a run TUI whose cached full snapshot is still inside the automatic refresh freshness window
**When**: the developer presses the manual refresh binding
**Then**: the TUI calls `RunController.snapshot()` immediately
**And**: the rendered state reflects the forced full refresh rather than waiting for throttle expiry

#### Scenario: Terminal run update bypasses throttle

**Given**: a run TUI whose cached full snapshot is still inside the automatic refresh freshness window
**When**: the run controller worker completes, is interrupted, or reports a terminal result
**Then**: the TUI renders the terminal state without waiting for the automatic refresh throttle window to expire

#### Scenario: Non-TUI run execution remains unchanged

**Given**: an active review session
**When**: the developer runs `review-gauntlet run --no-tui`
**Then**: run-controller execution, ready-task selection, adapter execution, finalization, interrupts, and error handling follow the existing non-TUI behavior
**And**: the TUI refresh throttle has no effect on non-TUI output
