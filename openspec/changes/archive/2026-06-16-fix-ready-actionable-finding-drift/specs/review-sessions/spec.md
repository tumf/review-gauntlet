## MODIFIED Requirements

### Requirement: Ready command SHALL emit the next skill-directed prompt

`review-gauntlet ready` SHALL emit the next skill-directed prompt from concrete renderable work items. It SHALL preserve deterministic priority across pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, stale review cells, and finalize readiness. When aggregate session counts and materialized prompt candidates disagree, `ready` SHALL skip empty candidate buckets and continue to the next valid action instead of crashing while building an impossible file-scoped prompt.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require ready prompt selection to be based on renderable review cells/findings, while preserving existing priority order and finalize fallback behavior. -->

#### Scenario: Ready skips empty actionable finding bucket

**Given**: an active review session whose aggregate finding counts report confirmed findings
**And**: the concrete ready finding rows available for prompt rendering contain no confirmed finding
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the command does not raise a traceback while selecting the target file
**And**: the command skips the empty confirmed-finding bucket
**And**: the command returns the next valid ready prompt or `null` when no promptable work remains

#### Scenario: Ready priority still uses concrete work

**Given**: an active review session with concrete pending review cells and concrete actionable findings
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the selected prompt corresponds to the first concrete available category in this order: pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, stale review cells, finalize
**And**: no category is selected unless it has at least one concrete renderable review cell or finding when that category requires file-scoped work

## ADDED Requirements

### Requirement: Run command SHALL preserve primary failure diagnostics

`review-gauntlet run` SHALL not mask a primary ready-prompt, controller, or adapter orchestration failure with a secondary result-handling error. If a run attempt cannot produce the normal result dictionary, command handling SHALL either emit a structured failure result when safe or propagate the original exception without replacing it with an unrelated `NoneType` or missing-key error.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require run command failure handling to preserve the original failure cause and avoid secondary result-shape crashes. -->

#### Scenario: Run does not mask ready failure with none result access

**Given**: an active review session where ready-prompt generation raises an unexpected exception before a run result is produced
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the command does not raise `TypeError: 'NoneType' object is not subscriptable`
**And**: the visible failure preserves the original ready-prompt or controller failure cause
**And**: the command does not report successful completion
