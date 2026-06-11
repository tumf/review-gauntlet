## MODIFIED Requirements

### Requirement: Review sessions SHALL persist durable state

`review-gauntlet` SHALL support durable review sessions stored under `.review-gauntlet/` at the reviewed repository root. A session SHALL preserve the target policy, active session metadata, ruleset identity, review universe state, immutable run history, review cells, findings, finding occurrences, and finding events. Target policy selection SHALL occur during `init`, not during `review`. The default `init` target SHALL be OCR-compatible workspace diff review; full-repository review SHALL require explicit `--all`. Review universe construction SHALL apply deterministic built-in artifact exclusions and default review-path exclusions, including `openspec/`, `tests/`, and `docs/`, before creating review cells. Review cell ledger identity SHALL be scoped to the owning session, so multiple sessions MAY contain the same deterministic review cell ID without corrupting or blocking each other.

#### Scenario: Initialize a second session with overlapping review cells

**Given**: a repository with an existing `.review-gauntlet/` ledger from a prior `review-gauntlet init`
**And**: the next requested target includes one or more files that produce the same deterministic review cell IDs as the prior session
**When**: the developer runs `review-gauntlet init --all`
**Then**: the CLI creates a new durable session
**And**: records review cells for the new session without failing on duplicate deterministic `cell_id` values from the prior session
**And**: keeps coverage and cell state scoped to each session

#### Scenario: Cell state update does not cross session boundary

**Given**: two review sessions contain the same deterministic review cell ID
**When**: review-gauntlet marks that cell reviewed, stale, or superseded for one session
**Then**: only the row for the intended session is updated
**And**: the other session's cell state remains unchanged

#### Scenario: Existing old-schema ledgers are not migrated

**Given**: a repository contains an old `.review-gauntlet/ledger.sqlite` schema where `review_cells.cell_id` is table-wide unique
**When**: this change is implemented
**Then**: review-gauntlet is not required to migrate or repair that old ledger automatically
**And**: users may recreate local review-gauntlet state if an old ledger blocks new sessions
