## MODIFIED Requirements

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL execute Phase 1: reviewing all pending review cells in a single invocation. A review invocation with no pending cells SHALL NOT create a run record. `review-gauntlet review` SHALL return structured failed-cell output when any adapter invocation fails. Successful cells from the same run SHALL still persist coverage and findings before the command exits, including successful cells completed before or during handling of a user interrupt.

#### Scenario: Zero-cell review does not create run record

**Given**: an active session whose current cells are already reviewed
**When**: the developer runs `review-gauntlet review`
**Then**: no new reviewed-cell coverage is recorded
**And**: no run record is created

#### Scenario: Partial adapter failure preserves successful cells

**Given**: a review run with 3 pending cells
**And**: one adapter invocation fails
**When**: the run completes
**Then**: successful cells are recorded as reviewed
**And**: findings from successful cells are persisted
**And**: the failed cell remains pending for retry

#### Scenario: Interrupted review preserves completed cells

**Given**: a review run with 3 pending cells
**And**: one cell adapter invocation has completed successfully before the user interrupt is handled
**When**: the developer interrupts `review-gauntlet review`
**Then**: the completed cell is recorded as reviewed
**And**: findings from the completed cell are persisted for the current run
**And**: cells that did not complete successfully remain pending for retry
**And**: the active session remains available for subsequent review commands

#### Scenario: Interrupted review drains already completed futures

**Given**: a parallel review run with multiple in-flight cell futures
**And**: future A is complete, future B is still running, and future C has not completed
**When**: interrupt handling begins
**Then**: future A is collected without waiting for future B or C
**And**: a successful outcome from future A is persisted as reviewed coverage
**And**: futures B and C are cancelled or left pending without being marked reviewed

<!-- Expected canonical result after archive: the review command requirement explicitly covers preserving completed cell coverage and findings during user interruption. -->
