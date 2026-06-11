## MODIFIED Requirements

### Requirement: Review cells SHALL model coverage independently from finding state

The CLI SHALL track review cells as review coverage units separate from finding triage state. A cell MAY be reviewed while the session remains incomplete because associated findings are not terminal. Review coverage for current cells SHALL be tied to the reviewed content digest: when a stale current cell is successfully reviewed again, the ledger SHALL refresh that cell's stored digest to the current digest so that unchanged content is not repeatedly marked stale.

#### Scenario: Reviewed cell with untriaged finding is not complete session

**Given**: a review cell has been reviewed and produced a finding
**When**: the finding remains `untriaged`
**Then**: the cell counts as reviewed for coverage
**But**: the session cannot finalize

#### Scenario: Changed target invalidates prior coverage

**Given**: an active moving-target session with previously reviewed cells
**When**: the target content changes before a later review run
**Then**: affected current cells are marked stale or superseded according to whether they remain in the current review universe
**And**: new current cells are added as pending when required

#### Scenario: Successful stale review refreshes the reviewed digest

**Given**: an active session where a previously reviewed current cell has become stale because its file content changed
**When**: a later `review-gauntlet review` run successfully reviews that current cell
**Then**: the cell is recorded as `reviewed`
**And**: the cell's stored content digest is refreshed to the current digest that was reviewed
**And**: a later review run without another file change does not mark that same cell stale again
**And**: the later review run can select remaining pending or stale cells according to normal budget order

#### Scenario: Unsuccessful stale review does not refresh coverage

**Given**: an active session where a previously reviewed current cell has become stale because its file content changed
**When**: a later `review-gauntlet review` run fails, is interrupted, or does not select that cell
**Then**: the cell is not recorded as refreshed reviewed coverage
**And**: the stale or pending coverage remains visible until a successful review evaluates the current cell
