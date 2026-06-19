## MODIFIED Requirements

### Requirement: Run controller SHALL support two-phase execution

`RunController.run()` SHALL execute the review session in two phases: Phase 1 (review all pending cells) and Phase 2 (resolve all open findings). Phase 2 SHALL NOT begin until Phase 1 succeeds with no remaining pending cells. Each phase SHALL consume one step count. The TUI SHALL display the current phase and SHALL expose Findings progress clearly while a run is active.

The run TUI SHALL render the Findings panel title as `Findings {resolved}/{total}` outside active review execution, where `total` is the current number of findings and `resolved` is the number that are no longer actionable. While Phase 1 review execution is actively running, the Findings panel title SHALL animate through `Finding`, `Finding.`, `Finding..`, and `Finding...` using the TUI activity frame. While Phase 2 resolution execution is actively running, the TUI SHALL keep the `Findings {resolved}/{total}` title and SHALL display a running indicator on each finding row targeted by the active resolve process.

The run TUI SHALL render a compact color legend that uses the same style sources as the body content for priority labels, finding-state labels, and finding-progress labels. The legend SHALL include samples for `P0`, `P1`, `P2`, `P3`, `open`, `confirmed`, `dismissed`, `done`, and `find`. Plain-text rendering of the legend SHALL remain readable and deterministic.

<!-- Expected canonical result after archive: the canonical run-controller spec will require the run TUI to expose the primary body color semantics in the legend, covering priority, finding-state, and finding-progress labels without changing run-controller behavior. -->

#### Scenario: Run executes Phase 1 then Phase 2

**Given**: an active session with pending cells
**When**: `review-gauntlet run` starts
**Then**: Phase 1 reviews all pending cells in parallel
**And**: Phase 2 begins after all cells are reviewed
**And**: the TUI displays the current phase

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

#### Scenario: Color legend matches body semantics

**Given**: the run TUI uses colored body text for priorities, finding states, and finding progress
**When**: the TUI renders the color legend
**Then**: the legend includes `P0`, `P1`, `P2`, and `P3` with the same styles used by priority labels in queue, rules, and files body rows
**And**: the legend includes `open`, `confirmed`, and `dismissed` with the same styles used by finding-state body rows
**And**: the legend includes `done` and `find` with the same style used by finding-progress counts
**And**: plain-text legend rendering remains readable without Rich styling
