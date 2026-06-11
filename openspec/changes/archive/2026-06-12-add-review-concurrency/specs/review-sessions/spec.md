## MODIFIED Requirements

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL advance the active session by one review run only. It SHALL recalculate the current review universe according to the active session's target policy, reconcile existing ledger state, review eligible cells within the configured budget, execute review work through the selected review adapter, update cell coverage only for successfully reviewed cells, record findings and occurrences, verify pending fixes when possible, and return the next required action without recursively continuing the session loop. It SHALL NOT accept target selection flags or retarget the active session.

The review command SHALL support a positive integer `--concurrency` option, defaulting to `8`, that limits how many selected review cells may execute adapter review work simultaneously within that one run. The concurrency option SHALL NOT change the review budget, selected-cell eligibility, target policy, or the requirement that coverage is recorded only for successfully executed cells.

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
