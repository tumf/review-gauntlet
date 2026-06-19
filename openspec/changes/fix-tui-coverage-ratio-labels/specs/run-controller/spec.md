## MODIFIED Requirements

### Requirement: Run controller SHALL support two-phase execution

`RunController.run()` SHALL execute the review session in two phases: Phase 1 (review all pending cells) and Phase 2 (resolve all open findings). Phase 2 SHALL NOT begin until Phase 1 succeeds with no remaining pending cells. Each phase SHALL consume one step count. The TUI SHALL display the current phase and SHALL expose Findings progress clearly while a run is active.

The run TUI SHALL render the Findings panel title as `Findings {resolved}/{total}` outside active review execution, where `total` is the current number of findings and `resolved` is the number that are no longer actionable. While Phase 1 review execution is actively running, the Findings panel title SHALL animate through `Finding`, `Finding.`, `Finding..`, and `Finding...` using the TUI activity frame. While Phase 2 resolution execution is actively running, the TUI SHALL keep the `Findings {resolved}/{total}` title and SHALL display a running indicator on each finding row targeted by the active resolve process.

The run TUI SHALL keep `Rule coverage` and `File hotlist` ratio displays compact while making their meaning visible through panel-local column headers rather than a footer/global color legend. Both panels SHALL use the same compact column vocabulary: `prio`, `target`, `cells`, and `fix`. The `cells` column SHALL mean reviewed cells / total cells. The `fix` column SHALL mean resolved findings / total findings. The run TUI SHALL NOT add a persistent footer/global color legend to explain these coverage ratios.

<!-- Expected canonical result after archive: the canonical run-controller spec will no longer require a compact color legend. It will require compact, panel-local column headers for Rule coverage and File hotlist ratio semantics. -->

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

#### Scenario: Rule coverage ratios use compact column headers

**Given**: the run TUI has rule coverage entries with reviewed cell counts and finding resolution counts
**When**: the TUI renders the Rule coverage panel
**Then**: the panel includes compact column headers `prio`, `target`, `cells`, and `fix`
**And**: each rule row renders priority, rule id, reviewed/total cells, and resolved/total findings under those columns
**And**: the row does not need long repeated labels to explain each ratio

#### Scenario: File hotlist ratios use the same compact column headers

**Given**: the run TUI has file coverage entries with reviewed cell counts and finding resolution counts
**When**: the TUI renders the File hotlist panel
**Then**: the panel includes compact column headers `prio`, `target`, `cells`, and `fix`
**And**: each file row renders priority, file path, reviewed/total cells, and resolved/total findings under those columns
**And**: the column vocabulary matches the Rule coverage panel

#### Scenario: Footer color legend is not required for coverage ratio meaning

**Given**: the run TUI renders Rule coverage and File hotlist panels
**When**: the user reads their ratio columns
**Then**: the meaning of `cells` and `fix` is available from the panel-local headers
**And**: the TUI does not add a persistent footer/global color legend for priority, finding-state, or finding-progress samples
