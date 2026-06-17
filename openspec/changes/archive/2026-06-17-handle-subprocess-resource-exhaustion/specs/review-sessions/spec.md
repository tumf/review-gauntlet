## ADDED Requirements

### Requirement: Review adapter startup failures SHALL be structured

When a command-backed review or verification attempt cannot start its external process because subprocess startup raises `OSError`, `review-gauntlet` SHALL report a structured failed-cell result instead of exposing a raw Python traceback as the final user-facing result. Resource exhaustion errors including `EMFILE` and `ENFILE` SHALL be distinguishable from missing-command startup failures and SHALL include actionable retry guidance.

#### Scenario: Adapter startup resource exhaustion is structured

**Given**: an active session with a selected review cell using the external command adapter
**And**: starting the adapter command raises `OSError` with `errno.EMFILE`
**When**: the developer runs `review-gauntlet review --format json`
**Then**: stdout contains a parseable failed-run JSON result with `failed_cell_id` and `failure` details
**And**: the failure details identify resource exhaustion rather than command-not-found
**And**: the failure details include actionable guidance to reduce concurrency or increase the open-file limit
**And**: the command exits non-zero without printing a raw traceback as the final user-facing result
**And**: the failed cell remains pending or stale for retry

#### Scenario: Concurrent review preserves successful sibling cells after startup exhaustion

**Given**: an active session with multiple selected review cells
**And**: one selected cell's external command startup raises `OSError` with `errno.EMFILE`
**And**: at least one other selected cell succeeds in the same run
**When**: the run finalizes
**Then**: successful selected cells are recorded as reviewed
**And**: findings and occurrences from successful cells are persisted
**And**: the failed cell remains non-reviewed and visible for later retry

### Requirement: Review and verification concurrency SHALL default to three

`review-gauntlet review` and `review-gauntlet verify-fixes` SHALL use a default concurrency of `3` when the developer does not pass `--concurrency`. Explicit positive `--concurrency` values SHALL continue to override the default and SHALL retain existing validation and worker-cap behavior.

#### Scenario: Review without explicit concurrency uses three workers

**Given**: an active session with enough eligible pending review cells for concurrent execution
**When**: the developer runs `review-gauntlet review` without `--concurrency`
**Then**: adapter review work executes for no more than three selected cells at the same time
**And**: review budget, selected-cell eligibility, target policy, and successful-cell-only coverage semantics remain unchanged

#### Scenario: Verify-fixes without explicit concurrency uses three workers

**Given**: an active session with enough fixed-pending findings for concurrent verification work
**When**: the developer runs `review-gauntlet verify-fixes` without `--concurrency`
**Then**: adapter verification work executes for no more than three selected cells at the same time
**And**: verification target selection and fixed-finding state transition semantics remain unchanged

#### Scenario: Explicit concurrency still overrides the default

**Given**: an active session with enough eligible cells for concurrent execution
**When**: the developer runs `review-gauntlet review --concurrency 2`
**Then**: adapter review work executes for no more than two selected cells at the same time
**And**: the default concurrency of `3` is not applied to that invocation

## MODIFIED Requirements

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL create durable run evidence only for review attempts that can evaluate selected cells. A review invocation with no selected current cells SHALL NOT create a run record that can satisfy finalization freshness or reviewed-target evidence. `review-gauntlet review` SHALL return structured failed-cell output when adapter work raises an unexpected exception or when adapter command startup fails from an operating-system startup error, not only when the adapter explicitly raises `ReviewAdapterError`. Successful cells from the same run SHALL still persist coverage, findings, occurrences, and applicable fixed-finding verification before the command exits non-zero.

#### Scenario: Zero-cell review does not refresh finalization evidence

**Given**: an active session whose current cells are already reviewed
**When**: the developer runs `review-gauntlet review --budget 1`
**Then**: no new reviewed-cell coverage is recorded
**And**: no zero-cell run is used as the last reviewed target digest for finalization

#### Scenario: Unexpected adapter exception is structured failure

**Given**: an active session where a selected review cell's adapter work raises an unexpected `RuntimeError`
**When**: `review-gauntlet review --format json` processes the run
**Then**: stdout contains a parseable failed-run JSON result with `failed_cell_id` and `failure` details
**And**: the command exits non-zero without printing a raw traceback as the final user-facing result
**And**: the failed cell remains pending or stale for retry

#### Scenario: Unexpected adapter exception preserves other successful cells

**Given**: a review run selects multiple cells
**And**: one selected cell raises an unexpected adapter exception
**And**: at least one other selected cell succeeds
**When**: the run finalizes
**Then**: successful selected cells are recorded as reviewed
**And**: the failed cell remains non-reviewed and visible for later retry
