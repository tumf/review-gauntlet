## MODIFIED Requirements

### Requirement: Review SHALL support parallel cell execution in Phase 1

`review-gauntlet review` SHALL execute pending review cells in parallel during Phase 1. By default, the command SHALL select all pending review cells. When one or more `--cell <cell-id>` options are supplied, the command SHALL restrict the run's selected cells to the requested cell IDs that are part of the active reconciled session and currently pending. Each cell's review adapter invocation SHALL be read-only with respect to the repository. Successful cells SHALL transition to `REVIEWED` state. Failed cells SHALL remain `PENDING` for retry. The `--parallel N` option SHALL control the maximum number of concurrent adapter invocations, defaulting to the number of available CPU cores.

#### Scenario: All pending cells reviewed in parallel by default

**Given**: an active session with 5 pending review cells
**When**: the developer runs `review-gauntlet review`
**Then**: all 5 cells are selected for review
**And**: selected cells are reviewed concurrently up to the configured parallelism limit
**And**: successful cells are marked `REVIEWED`
**And**: findings from all successful cells are persisted with state `open`
**And**: the command exits 0 when all selected cells succeed

#### Scenario: Explicit cell selector reviews only requested pending cells

**Given**: an active session with pending review cells `RGC-a`, `RGC-b`, and `RGC-c`
**When**: the developer runs `review-gauntlet review --cell RGC-b --format json`
**Then**: only cell `RGC-b` is selected for adapter invocation
**And**: successful review marks `RGC-b` as `REVIEWED`
**And**: cells `RGC-a` and `RGC-c` remain `PENDING`
**And**: JSON output remains parseable and reports the resulting session status

#### Scenario: Duplicate explicit cell selectors do not duplicate review work

**Given**: an active session with pending review cell `RGC-a`
**When**: the developer runs `review-gauntlet review --cell RGC-a --cell RGC-a`
**Then**: cell `RGC-a` is selected at most once
**And**: the review adapter is invoked at most once for `RGC-a`

#### Scenario: Unknown explicit cell selector is rejected before adapter work

**Given**: an active session whose reconciled cells do not include `RGC-missing`
**When**: the developer runs `review-gauntlet review --cell RGC-missing`
**Then**: the command fails with usage-error semantics
**And**: the diagnostic names `RGC-missing`
**And**: no review adapter command is invoked
**And**: no new run is created for the rejected request

#### Scenario: Already-reviewed explicit cell selector is a no-op for that cell

**Given**: an active session where cell `RGC-a` is already `REVIEWED`
**When**: the developer runs `review-gauntlet review --cell RGC-a`
**Then**: cell `RGC-a` is not selected for adapter invocation
**And**: its state remains `REVIEWED`
**And**: if no requested pending cells remain, the command exits 0 with the normal zero-selected review output

#### Scenario: Partial failure preserves coverage

**Given**: an active session with 3 pending review cells
**And**: one adapter invocation fails with an unexpected error
**When**: `review-gauntlet review --format json` completes
**Then**: the successful cells are marked `REVIEWED`
**And**: the failed cell remains `PENDING`
**And**: findings from successful cells are persisted
**And**: the command exits non-zero with structured failure details

#### Scenario: Zero pending cells is a no-op

**Given**: an active session where all cells are already `REVIEWED`
**When**: the developer runs `review-gauntlet review`
**Then**: no new run record is created
**And**: no adapter commands are invoked
**And**: the command exits 0

<!-- Expected canonical result after archive: the review-sessions spec will require `review-gauntlet review` to keep default all-pending Phase 1 behavior while allowing repeatable `--cell` selectors that restrict execution to known pending review cells and reject unknown cell IDs before adapter work. -->
