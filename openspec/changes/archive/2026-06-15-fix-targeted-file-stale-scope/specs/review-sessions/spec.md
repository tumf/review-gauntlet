## MODIFIED Requirements

### Requirement: Review cells SHALL model coverage independently from finding state

Review cell state mutations SHALL be durable and explicit. Attempts to update a review cell state for an unknown session/cell pair SHALL fail rather than silently succeeding with zero changed rows. File freshness refreshes for a successfully evaluated targeted path SHALL update the stored content digest for all cells on that path without changing unselected sibling cell states.

#### Scenario: Unknown review cell update fails

**Given**: a session ledger without cell `RGC-missing`
**When**: internal reconciliation attempts to update `RGC-missing`
**Then**: the store raises an actionable lookup error
**And**: no caller can treat the missing cell as updated coverage

#### Scenario: Targeted file sibling freshness refresh preserves coverage states

**Given**: an active session with multiple review cells for `file1`
**And**: one `file1` cell is selected and successfully evaluated after `file1` changes
**When**: coverage is reconciled after that successful evaluation
**Then**: all `file1` cells store the current `file1` content digest
**And**: unselected `file1` sibling cells are not marked `stale` solely because `file1` changed
**And**: unselected sibling cells keep their prior coverage states

#### Scenario: Incidental changed files become stale

**Given**: an active session with reviewed cells for `file1` and `file2`
**And**: the current successful review or verification step targets `file1`
**When**: both `file1` and `file2` have changed since their recorded coverage
**Then**: `file1` cells are not stale solely because `file1` was intentionally changed and evaluated
**And**: `file2` cells are stale because `file2` changed incidentally outside the targeted evaluation
**And**: stale `file2` coverage remains visible as a finalization blocker

### Requirement: Verify-fixes command SHALL re-review fixed findings explicitly

`review-gauntlet verify-fixes` SHALL provide a dedicated post-fix verification command for findings in `fixed_pending_verification`. The command SHALL execute at most one verification run, SHALL use the existing review adapter verdict contract, SHALL only target fixed-pending findings selected by optional filters, and SHALL keep findings that cannot be evaluated visible rather than treating them as verified. When a fixed-pending finding path is successfully evaluated, the command SHALL refresh file freshness for all review cells on that targeted path without selecting unrelated pending or stale cells.

#### Scenario: Verify fixes verifies absent findings

**Given**: an active session with a finding in `fixed_pending_verification`
**And**: the finding's path maps to a current review cell
**And**: the verification adapter returns no comment with the finding's fingerprint
**When**: the developer runs `review-gauntlet verify-fixes --format json`
**Then**: the command executes a verification run for the relevant current review cell
**And**: the finding transitions to `fixed_verified`
**And**: stdout contains parseable JSON listing the finding ID in `fixed_verified_ids`
**And**: the command exits `0`

#### Scenario: Verify fixes reopens redetected findings

**Given**: an active session with a finding in `fixed_pending_verification`
**And**: the finding's path maps to a current review cell
**And**: the verification adapter returns a comment that normalizes to the same finding fingerprint
**When**: the developer runs `review-gauntlet verify-fixes --format json`
**Then**: the finding transitions to `reopened`
**And**: the finding does not transition to `fixed_verified` in the same run
**And**: stdout contains parseable JSON listing the finding ID in `reopened_ids`
**And**: the command exits `1`

#### Scenario: Verify fixes targets only fixed-pending findings

**Given**: an active session with pending review cells and findings in `confirmed`, `reopened`, `fixed_pending_verification`, and terminal states
**When**: the developer runs `review-gauntlet verify-fixes --format json`
**Then**: adapter execution is limited to current cells needed by `fixed_pending_verification` findings
**And**: unrelated pending or stale review cells are not selected merely to advance coverage
**And**: non-fixed-pending findings are not mutated

#### Scenario: Verify fixes refreshes targeted path sibling freshness

**Given**: an active session with multiple review cells for a path that has a finding in `fixed_pending_verification`
**And**: that path changed while fixing the finding
**When**: `review-gauntlet verify-fixes --format json` successfully evaluates the current review cell for that finding path
**Then**: the finding may transition according to the verification verdict
**And**: all review cells on that targeted path store the current content digest
**And**: unselected sibling cells on that same path are not marked `stale` solely because the targeted path changed
**And**: unrelated pending or stale cells on other paths are not selected merely to refresh freshness

#### Scenario: Verify fixes supports focused finding and path filters

**Given**: an active session with multiple findings in `fixed_pending_verification` across multiple repository paths
**When**: the developer runs `review-gauntlet verify-fixes --finding RGF-0001 --path src/app.py --format json`
**Then**: only fixed-pending findings matching the requested finding ID and repository path filter are targeted
**And**: repeated `--finding` values match any listed finding ID
**And**: repeated `--path` values match any listed safe repository path or prefix

#### Scenario: Verify fixes rejects unsafe path filters before execution

**Given**: an active session with fixed-pending findings
**When**: the developer runs `review-gauntlet verify-fixes --path ../src`
**Then**: the command fails with a usage error
**And**: no adapter command is executed
**And**: no run or finding event is written

#### Scenario: Verify fixes no-op does not refresh evidence

**Given**: an active session with matching fixed-pending findings
**When**: the developer runs `review-gauntlet verify-fixes --budget 0 --format json`
**Then**: no verification run is created
**And**: no finding state is modified
**And**: stdout reports the targeted finding IDs as still requiring verification

#### Scenario: Verify fixes reports unverifiable findings

**Given**: an active session with a fixed-pending finding whose path cannot be successfully evaluated
**When**: the developer runs `review-gauntlet verify-fixes --format json`
**Then**: the finding remains `fixed_pending_verification`
**And**: stdout contains parseable JSON listing the finding ID in `unverifiable_ids`
**And**: the command exits `1`
