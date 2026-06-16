## MODIFIED Requirements

### Requirement: Ready command SHALL emit the next skill-directed prompt

#### Scenario: Ready prompt priority is deterministic

**Given**: an active review session with multiple kinds of incomplete work
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the selected prompt corresponds to the first available category in this order: pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, stale review cells, finalize
**And**: finding prompts remain reachable after review-cell coverage is complete.

### Requirement: Verify-fixes command SHALL re-review fixed findings explicitly

#### Scenario: Verify fixes refreshes targeted path sibling freshness

**Given**: an active session with multiple review cells for a path that has a finding in `fixed_pending_verification`
**And**: that path changed while fixing the finding
**When**: `review-gauntlet verify-fixes --format json` successfully evaluates the current review cell for that finding path
**Then**: the finding may transition according to the verification verdict
**And**: all review cells on that targeted path store the current content digest
**And**: unselected sibling cells on that same path are not marked `stale` solely because the targeted path changed
**And**: unselected sibling cells on that same path are not promoted to `pending` solely because the targeted path was evaluated
**And**: unrelated pending or stale cells on other paths are not selected merely to refresh freshness
