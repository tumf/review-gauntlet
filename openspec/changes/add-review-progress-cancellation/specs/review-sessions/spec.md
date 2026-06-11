## MODIFIED Requirements

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL advance the active session by one review run only. It SHALL recalculate the current review universe according to the active session's target policy, reconcile existing ledger state, review eligible cells within the configured budget, execute review work through the selected review adapter, update cell coverage only for successfully reviewed cells, record findings and occurrences, verify pending fixes when possible, and return the next required action without recursively continuing the session loop. It SHALL NOT accept target selection flags or retarget the active session.

The review command SHALL support a positive integer `--concurrency` option, defaulting to `8`, that limits how many selected review cells may execute adapter review work simultaneously within that one run. The concurrency option SHALL NOT change the review budget, selected-cell eligibility, target policy, or the requirement that coverage is recorded only for successfully executed cells.

For human-audience runs, the review command SHALL expose review-run and per-cell progress on stderr while adapter work is in progress. Progress output SHALL NOT pollute stdout final output. Agent-audience output SHALL suppress decorative progress. If the user interrupts the command, the review command SHALL cancel pending work, terminate in-flight command adapter subprocesses when possible, and leave unfinished cells in a non-reviewed state.

#### Scenario: Review advances once with remaining pending work

**Given**: an active session with more pending review cells than the current review budget
**When**: the developer runs `review-gauntlet review`
**Then**: the CLI creates exactly one immutable run record
**And**: reviews only the cells selected for that run
**And**: leaves remaining eligible cells pending
**And**: reports that the next required action is to run review again or triage findings, depending on the run result

#### Scenario: Review rejects target selection flags

**Given**: an active session
**When**: the developer runs `review-gauntlet review --from main --to HEAD`, `review-gauntlet review --commit abc123`, `review-gauntlet review --worktree`, or `review-gauntlet review --all`
**Then**: argument parsing fails with a usage error
**And**: the active session target policy is not changed
**And**: no review run is created

#### Scenario: Review executes selected cells with bounded concurrency

**Given**: an active session with multiple eligible pending review cells
**And**: the current review budget permits multiple cells in the run
**When**: the developer runs `review-gauntlet review --concurrency 2`
**Then**: the CLI creates exactly one immutable run record
**And**: selects eligible cells deterministically up to the configured budget
**And**: executes adapter review work for no more than two selected cells at the same time
**And**: applies findings, occurrences, and cell coverage updates deterministically for successfully reviewed cells

#### Scenario: Review rejects invalid concurrency

**Given**: an active session
**When**: the developer runs `review-gauntlet review --concurrency 0`
**Then**: argument handling fails with a usage error
**And**: no adapter review work is executed
**And**: no cell is marked reviewed because of that command

#### Scenario: Concurrent review preserves budget semantics

**Given**: an active session with more eligible review cells than the current review budget
**When**: the developer runs `review-gauntlet review --budget 1 --concurrency 8`
**Then**: the CLI selects at most one cell for that run
**And**: reviews at most one cell even though the concurrency limit is higher than the budget
**And**: leaves remaining eligible cells pending

#### Scenario: Concurrent review preserves failed-cell visibility

**Given**: an active session with multiple selected review cells
**And**: the selected review adapter fails for one selected cell
**When**: the developer runs `review-gauntlet review --concurrency 2 --format json`
**Then**: the CLI exits non-zero and reports the failed cell id, error, failure details, and current session status
**And**: the failed cell is not marked reviewed
**And**: successful cells whose results were committed are recorded explicitly in coverage and findings state

#### Scenario: Human review reports progress without corrupting final output

**Given**: an active session with selected review cells
**When**: the developer runs `review-gauntlet review --format json`
**Then**: the CLI writes run and per-cell progress to stderr while adapter work is in progress
**And**: stdout remains exactly one parseable final JSON result
**And**: the progress includes the run id, selected cell count, concurrency, adapter identity when available, and cell start/completion or failure events

#### Scenario: Agent audience suppresses decorative review progress

**Given**: an active session with selected review cells
**When**: automation runs `review-gauntlet review --format json --audience agent`
**Then**: stdout contains only the final parseable JSON result
**And**: decorative progress text is not emitted for the agent audience

#### Scenario: Interrupted review cancels unfinished work visibly

**Given**: an active session with multiple selected review cells
**And**: at least one selected command adapter subprocess is still running
**When**: the developer interrupts `review-gauntlet review`
**Then**: the CLI cancels pending adapter work and terminates in-flight command adapter subprocesses when possible
**And**: cells that did not complete successfully are not marked reviewed
**And**: any cancellation or termination artifacts available for those cells are recorded under the run artifacts directory
**And**: any successful cells whose results were already committed remain recorded in the ledger
