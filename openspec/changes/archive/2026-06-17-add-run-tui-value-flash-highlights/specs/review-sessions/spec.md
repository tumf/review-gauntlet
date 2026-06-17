## ADDED Requirements

### Requirement: Run TUI SHALL flash-highlight only changed display values

`review-gauntlet run` interactive TUI SHALL make meaningful display updates visible by temporarily flash-highlighting only the changed value or narrowest practical semantic display fragment. The highlight SHALL NOT expand to the entire containing panel when a smaller changed value can be identified. This visual behavior SHALL be limited to the TUI render path and SHALL NOT change non-TUI text output, JSON output, run controller state, session state, finding state, or finalization behavior.

#### Scenario: Coverage completed count highlights without panel-wide flash

**Given**: the run TUI has rendered a Session summary showing coverage `0 / 2`
**When**: the next TUI refresh renders coverage `1 / 2`
**Then**: the changed completed-count value is flash-highlighted
**And**: the unchanged total value is not flash-highlighted solely because the completed count changed
**And**: the containing Session panel is not flash-highlighted as a whole

#### Scenario: Agent step highlights only the changed value

**Given**: the run TUI has rendered `Agent step 1`
**When**: the next TUI refresh renders `Agent step 2`
**Then**: the displayed step value `2` is flash-highlighted
**And**: the entire Agent or Session panel is not flash-highlighted solely because the step value changed

#### Scenario: Finding counts highlight only changed counts

**Given**: the run TUI has rendered a finding summary with zero actionable open findings
**When**: the next TUI refresh renders a non-zero actionable finding count
**Then**: the changed finding count or narrowest practical count fragment is flash-highlighted
**And**: unchanged summary labels are not flash-highlighted solely because the count changed

#### Scenario: Finalize checklist highlights changed gate fields

**Given**: the run TUI has rendered the finalize checklist
**When**: a gate marker, state, or detail changes on the next TUI refresh
**Then**: the changed gate field or narrowest practical detail fragment is flash-highlighted
**And**: unrelated gates are not flash-highlighted
**And**: the entire checklist panel is not flash-highlighted solely because one gate field changed

#### Scenario: Volatile time counters do not trigger flash highlights

**Given**: the run TUI has rendered quiet duration, last-output age, timeout countdown, elapsed time, or a spinner frame
**When**: the next TUI refresh changes only those time-counter or spinner values
**Then**: no flash highlight is triggered for those natural refresh changes

#### Scenario: Meaningful status-kind changes still trigger flash highlights

**Given**: the run TUI has rendered an agent liveness or timeout display kind
**When**: the next TUI refresh changes the display kind, such as from running to quiet or from timeout not configured to timeout countdown
**Then**: the changed status or timeout kind is flash-highlighted
**And**: subsequent numeric duration or countdown drift does not keep retriggering the flash

#### Scenario: Activity timeline highlights new rows without timestamp-only flash

**Given**: the run TUI has rendered an Activity timeline
**When**: a new run event or agent output row appears on the next TUI refresh
**Then**: the new row or its new semantic detail is flash-highlighted
**And**: timestamp-only changes do not trigger a flash highlight
