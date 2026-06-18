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

### Requirement: Run controller SHALL include next_required_action in step_started events

`RunController.run()` SHALL include the `next_required_action` string in every `step_started` event payload alongside the existing `step` and `prompt` fields. The `next_required_action` value SHALL come from the same readiness context that produced the ready prompt, ensuring the TUI can classify the step without parsing prompt text. The ready-prompt callable SHALL return both the prompt text and the `next_required_action` as a single structured object so the two values cannot drift.

<!-- Expected canonical result after archive: the canonical run-controller spec will require step_started events to carry next_required_action and the ready-prompt callable to return a structured object containing both prompt and action. -->

#### Scenario: step_started event carries next_required_action

**Given**: a `RunController` with an active session and a ready task
**When**: `RunController.run()` emits a `step_started` event
**Then**: the event payload contains `step`, `prompt`, and `next_required_action` keys
**And**: `next_required_action` is a non-empty string matching the status-derived action for the current session state

#### Scenario: Ready-prompt callable returns structured ReadyTask

**Given**: a `RunController` constructed with a ready-prompt callable
**When**: the controller calls the callable during `run()` or `snapshot()`
**Then**: the callable returns a `ReadyTask` (or equivalent structured object) containing both `prompt` and `next_required_action`
**And**: both fields are derived from the same readiness context

### Requirement: Run controller SHALL support two-phase execution

`RunController.run()` SHALL execute the review session in two phases: Phase 1 (review all pending cells) and Phase 2 (resolve all open findings). Phase 2 SHALL NOT begin until Phase 1 succeeds with no remaining pending cells. Each phase SHALL consume one step count. The TUI SHALL display the current phase and SHALL expose Findings progress clearly while a run is active.

The run TUI SHALL render the Findings panel title as `Findings {resolved}/{total}` outside active review execution, where `total` is the current number of findings and `resolved` is the number that are no longer actionable. While Phase 1 review execution is actively running, the Findings panel title SHALL animate through `Finding`, `Finding.`, `Finding..`, and `Finding...` using the TUI activity frame. While Phase 2 resolution execution is actively running, the TUI SHALL keep the `Findings {resolved}/{total}` title and SHALL display a running indicator on each finding row targeted by the active resolve process.

<!-- Expected canonical result after archive: the canonical run-controller spec will require run TUI Findings progress titles and active resolve row indicators in addition to current phase display. -->

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

#### Scenario: Findings title shows resolved progress when not reviewing

**Given**: a run TUI snapshot with 3 findings
**And**: 2 of those findings are no longer actionable
**When**: the TUI renders the overview or findings view outside active review execution
**Then**: the Findings panel title is `Findings 2/3`

#### Scenario: Findings title animates during active review execution

**Given**: a run TUI snapshot whose agent status is `running`
**And**: the active step action is `run_review`
**When**: the TUI renders successive activity frames 0, 1, 2, and 3
**Then**: the Findings panel title cycles through `Finding`, `Finding.`, `Finding..`, and `Finding...`

#### Scenario: Resolve execution preserves Findings progress title

**Given**: a run TUI snapshot whose agent status is `running`
**And**: the active step action is `resolve_findings`
**And**: the snapshot has 3 findings with 1 resolved finding
**When**: the TUI renders the overview or findings view
**Then**: the Findings panel title is `Findings 1/3`
**And**: the title is not replaced by the review-phase `Finding...` animation

#### Scenario: Active resolve targets show row indicators

**Given**: a run TUI snapshot whose agent status is `running`
**And**: the active step action is `resolve_findings`
**And**: the active target finding IDs include `RGF-0001`
**And**: the Findings list includes `RGF-0001` and `RGF-0002`
**When**: the TUI renders finding rows
**Then**: the `RGF-0001` row displays a running indicator
**And**: the `RGF-0002` row displays no running indicator
**And**: both rows remain column-aligned

#### Scenario: Resolve row indicators clear after step completion

**Given**: a prior running snapshot showed active target finding ID `RGF-0001`
**When**: the agent step finishes and the TUI renders a refreshed snapshot
**Then**: no finding row displays the active running indicator

### Requirement: Resolve command SHALL require an active session before startup

`review-gauntlet resolve` SHALL verify that an active review session exists before loading adapter configuration or executing resolution agents. When no active session exists, it SHALL fail through the same actionable no-active-session diagnostic used by other session-scoped commands.

#### Scenario: Resolve without init stops before agent startup

**Given**: a repository root with no `.review-gauntlet/active-session.json`
**When**: the developer runs `review-gauntlet resolve`
**Then**: the command exits with code `1`
**And**: stderr contains `no active review session; run review-gauntlet init`

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

### Requirement: Run controller SHALL stop no-op successful verdict loops with actionable context

`RunController.run()` SHALL compare targeted session state before and after a successful progress verdict. If the verdict reports progress but the targeted state is unchanged, the controller SHALL stop the run with `reason: no_progress` instead of re-running the same ready task indefinitely. The returned failure metadata SHALL identify the task key, targeted IDs when known, and the artifact path or equivalent run evidence needed to inspect the no-op verdict.

#### Scenario: Successful-looking verdict with unchanged target state stops as no progress

**Given**: an active session with an open finding targeted by the current ready task
**And**: the external agent writes a syntactically successful `finish` verdict
**And**: applying the verdict leaves the targeted finding state unchanged
**When**: `RunController.run()` compares the pre-step and post-step targeted state
**Then**: the run returns `completed: false`
**And**: the result reason is `no_progress`
**And**: the failure metadata identifies the targeted finding ID or task key
**And**: the controller does not immediately execute the same ready task again

#### Scenario: No-progress context points to preserved verdict evidence

**Given**: a run step writes a verdict artifact that does not change targeted state
**When**: the controller reports `no_progress`
**Then**: the lifecycle or failure context includes the run artifact path or equivalent evidence location
**And**: a developer can inspect the preserved artifact to diagnose the no-op verdict
