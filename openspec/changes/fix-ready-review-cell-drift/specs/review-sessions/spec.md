## MODIFIED Requirements

### Requirement: Ready command SHALL emit the next skill-directed prompt

`review-gauntlet ready` SHALL emit the next skill-directed prompt from concrete renderable work items. It SHALL preserve deterministic priority across pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, stale review cells, and finalize readiness. When aggregate session counts and materialized prompt candidates disagree, `ready` SHALL skip empty candidate buckets and continue to the next valid action instead of crashing while building an impossible file-scoped prompt.

<!-- Expected canonical result after archive: the canonical review-sessions spec will include explicit review-cell bucket drift scenarios in addition to existing finding bucket drift coverage, requiring pending/stale prompt selection to be based on materialized review cells. -->

#### Scenario: Ready skips empty actionable finding bucket

**Given**: an active review session whose aggregate finding counts report confirmed findings
**And**: the concrete ready finding rows available for prompt rendering contain no confirmed finding
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the command does not raise a traceback while selecting the target file
**And**: the command skips the empty confirmed-finding bucket
**And**: the command returns the next valid ready prompt or `null` when no promptable work remains

#### Scenario: Ready skips empty pending review-cell bucket

**Given**: an active review session whose aggregate coverage counts report pending review cells
**And**: the concrete ready review-cell rows available for prompt rendering contain no pending review cell
**And**: a later-priority concrete actionable finding exists
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the command does not raise a traceback while selecting the target file
**And**: the command skips the empty pending review-cell bucket
**And**: the command returns the later-priority concrete finding prompt

#### Scenario: Ready skips empty stale review-cell bucket

**Given**: an active review session whose aggregate coverage counts report stale review cells
**And**: the concrete ready review-cell rows available for prompt rendering contain no stale review cell
**And**: no concrete actionable review cell or finding exists
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the command does not raise a traceback while selecting the target file
**And**: the command skips the empty stale review-cell bucket
**And**: the command returns `null` when finalization remains blocked by non-promptable state

#### Scenario: Ready priority still uses concrete work

**Given**: an active review session with concrete pending review cells and concrete actionable findings
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the selected prompt corresponds to the first concrete available category in this order: pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, stale review cells, finalize
**And**: no category is selected unless it has at least one concrete renderable review cell or finding when that category requires file-scoped work
