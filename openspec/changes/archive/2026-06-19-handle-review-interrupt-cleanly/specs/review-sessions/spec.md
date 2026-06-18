## MODIFIED Requirements

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL execute Phase 1: reviewing all pending review cells in a single invocation. A review invocation with no pending cells SHALL NOT create a run record. `review-gauntlet review` SHALL return structured failed-cell output when any adapter invocation fails. Successful cells from the same run SHALL still persist coverage and findings before the command exits, including successful cells completed before or during handling of a user interrupt.

When `review-gauntlet review` is interrupted by the user, the command SHALL exit with status code `130` and SHALL NOT output a raw Python traceback. If `--format json` is used, stdout SHALL contain parseable JSON that includes `interrupted: true`. The active session SHALL remain available for retry after interruption.

#### Scenario: Interrupted review exits without traceback

**Given**: `review-gauntlet review` is executing with pending cells
**When**: the user interrupts with `Ctrl-C`
**Then**: the command exits with status code `130`
**And**: stderr does not contain `Traceback`
**And**: stderr does not contain an uncaught `KeyboardInterrupt` stack trace

#### Scenario: Interrupted review emits structured JSON output

**Given**: `review-gauntlet review --format json` is executing
**When**: the user interrupts with `Ctrl-C`
**Then**: stdout is parseable JSON
**And**: the JSON object includes `"interrupted": true`
**And**: the JSON object includes `run_id`, `reviewed_cells`, and standard status fields

#### Scenario: Active session survives interrupt for retry

**Given**: a review run is interrupted after adapter cancellation and result persistence
**When**: the developer checks session state
**Then**: the active session remains available
**And**: the developer can run `review-gauntlet review` again without re-initialization

<!-- Expected canonical result after archive: the review command requirement explicitly mandates structured interrupt exit with code 130, no traceback, parseable JSON with interrupted flag, and active session preservation. -->
