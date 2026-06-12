## MODIFIED Requirements

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL advance the active session by one review run only. It SHALL recalculate the current review universe according to the active session's target policy, reconcile existing ledger state, review eligible cells within the configured budget, execute review work through the selected review adapter, update cell coverage only for successfully reviewed cells, record findings and occurrences, verify pending fixes when possible, and return the next required action without recursively continuing the session loop. It SHALL NOT accept target selection flags or retarget the active session.

The review command SHALL support a positive integer `--concurrency` option, defaulting to `8`, that limits how many selected review cells may execute adapter review work simultaneously within that one run. The concurrency option SHALL NOT change the review budget, selected-cell eligibility, target policy, or the requirement that coverage is recorded only for successfully executed cells.

The review command SHALL support `--format text|json`, defaulting to `text`. For default human-audience runs, the review command SHALL expose review-run and per-cell progress on stderr while adapter work is in progress. Progress output SHALL NOT pollute stdout final output. When `--audience agent` is explicitly selected, the review command SHALL suppress decorative progress because agent callers do not need progress display. If the user interrupts the command, the review command SHALL cancel pending work, terminate in-flight command adapter subprocesses when possible, and leave unfinished cells in a non-reviewed state.

If one or more selected cells fail after other selected cells have completed successfully, the review command SHALL persist coverage, findings, occurrences, and applicable fixed-finding verification for the successful cells before returning a failed command result. Failed cells SHALL remain non-reviewed and visible for later retry.

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

#### Scenario: Review rejects obsolete human format option

**Given**: an active session
**When**: the developer runs `review-gauntlet review --format human`
**Then**: the command fails with a usage error

#### Scenario: Partial failure preserves successful coverage

**Given**: an active session where a review run selects multiple cells
**And**: at least one selected cell succeeds
**And**: at least one selected cell fails in the same run
**When**: `review-gauntlet review` finalizes that run
**Then**: every successful selected cell is recorded as reviewed with its findings and occurrences
**And**: the final output reports the number of successful cells persisted in `reviewed_cells`
**And**: the command exits with a failure result that identifies a failed cell
**And**: failed cells remain pending or stale for later retry

#### Scenario: Partial failure verifies only successful paths

**Given**: an active session with fixed findings awaiting verification on two paths
**And**: a review run succeeds for one path and fails for the other path
**When**: `review-gauntlet review` finalizes that partial run
**Then**: fixed-finding verification may update the finding for the successfully evaluated path
**And**: the finding for the failed path remains `fixed_pending_verification`
