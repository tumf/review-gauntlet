## ADDED Requirements

### Requirement: Run TUI overview SHALL show actionable coverage projections instead of the full matrix

`review-gauntlet run` interactive TUI SHALL treat the full file × rule coverage matrix as internal session state and SHALL NOT render the complete matrix in the overview screen. The overview SHALL display actionable projections derived from current review cells and live findings: session status, coverage summary, finalize blockers, prioritized next review queue, rule coverage summary, file hotlist, open findings, and recent activity. The overview SHALL preserve the existing finalization, coverage, finding, and non-TUI output semantics.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require the run TUI overview to render queue/aggregate/hotlist projections rather than a wide file-by-rule matrix. -->

#### Scenario: Overview prioritizes the next review queue

**Given**: an active review session with pending cells, stale cells, and actionable findings
**When**: `review-gauntlet run` renders the interactive overview screen
**Then**: the overview displays a prioritized next review queue derived from concrete current review cells
**And**: the queue includes file path, rule ID, review state, priority label, and a concise reason for each visible entry
**And**: the overview does not render every file × rule cell as a complete matrix

#### Scenario: Overview shows rule and file aggregates

**Given**: an active review session with multiple files and rules
**When**: `review-gauntlet run` renders the interactive overview screen at a width that can fit aggregate panels
**Then**: the overview displays rule-level coverage summaries with reviewed, pending, stale, and open-finding counts
**And**: the overview displays a file hotlist with coverage, pending, stale, and finding counts
**And**: the aggregate lists are sorted deterministically so the riskiest or least-complete entries are visible first

#### Scenario: Narrow overview remains actionable

**Given**: an active review session in a narrow terminal
**When**: `review-gauntlet run` renders the interactive overview screen
**Then**: the overview prioritizes session status, coverage summary, finalize blockers, next review queue, and activity
**And**: lower-priority aggregate panels are compacted, stacked, or omitted rather than forcing a wide matrix layout
**And**: the controls explain how to navigate to focused detail views for files, rules, cells, findings, and agent state

### Requirement: Run TUI SHALL provide focused drill-down coverage views

`review-gauntlet run` interactive TUI SHALL provide focused views for file, rule, cell, finding, and agent detail navigation. Matrix-like coverage inspection SHALL be available through file-scoped, rule-scoped, or flat cell table views rather than through the overview screen. The existing stop, interrupt, refresh, and help controls SHALL remain available.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require focused coverage drill-down views while keeping the overview compact and actionable. -->

#### Scenario: Files view shows selected file rule states

**Given**: an active review session with review cells for multiple files
**When**: the developer opens the files view and selects a file
**Then**: the TUI shows that file's rule states and associated finding/evidence summary
**And**: it does not require displaying unrelated files' rule states in the same table

#### Scenario: Rules view shows selected rule file states

**Given**: an active review session with review cells for multiple rules
**When**: the developer opens the rules view and selects a rule
**Then**: the TUI shows files relevant to that rule with their review states and finding counts
**And**: it does not require displaying unrelated rules in the same detail table

#### Scenario: Cells view exposes all cells as a filterable flat table

**Given**: an active review session with many file × rule cells
**When**: the developer opens the cells view
**Then**: the TUI shows cells as a flat sortable or filterable table with state, priority, rule, file, and finding columns
**And**: filters can narrow the table to stale cells, pending cells, blockers, a rule, a file prefix, or open findings

### Requirement: Run TUI review queue priorities SHALL be deterministic and actionable

`review-gauntlet run` interactive TUI SHALL assign deterministic priority labels to review-cell queue entries. The displayed label SHALL be one of P0, P1, P2, or P3, derived from an internal score or equivalent deterministic ordering. Raw scores SHALL NOT be required in the overview display. Actionable findings, stale cells, pending cells, high-risk rules, changed files, and finding counts SHALL influence ordering so the queue identifies finalization blockers and high-value review work first.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require deterministic actionable priority labels for the run TUI review queue. -->

#### Scenario: Findings and stale cells sort ahead of normal pending cells

**Given**: an active review session with a normal pending cell, a stale cell, and a cell with an actionable finding
**When**: the run TUI builds the next review queue
**Then**: the cell with an actionable finding is labeled P0 and appears before normal pending cells
**And**: the stale cell appears before normal pending cells
**And**: entries with equal priority are ordered deterministically by stable cell attributes

#### Scenario: Queue labels hide raw scoring details

**Given**: an active review session with prioritized review queue entries
**When**: the run TUI renders the overview queue
**Then**: the overview displays P0, P1, P2, or P3 labels
**And**: it does not require exposing raw numeric priority scores to the developer
