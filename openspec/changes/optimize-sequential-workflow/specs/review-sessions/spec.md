## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

`findings --path` filters SHALL accept only repository-relative paths and directory prefixes. Absolute paths and parent-directory traversal SHALL fail with a usage error so filtering semantics remain repository-scoped and deterministic.

`findings` SHALL cap emitted findings to 10 records by default after applying terminal visibility, path filters, and mark filters. `findings --limit N` SHALL cap emitted findings to the requested positive integer limit. `findings --all-findings` SHALL disable the result-size cap without changing terminal visibility. `findings --limit N --all-findings` SHALL fail with a usage error.

`findings` SHALL expose count metadata in both structured and text result payloads. `total` SHALL be the number of findings after terminal visibility, path, and mark filters but before result-size limiting. `returned` SHALL be the number of findings actually emitted. Findings SHALL be ordered deterministically by path, start line, end line, and finding ID before any result-size cap is applied.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. `status` SHALL report `coverage` as an effective read-only view of the active session's current target rather than a raw persisted review-cell count. Effective coverage SHALL be derived by comparing current target cells and current file digests against persisted review-cell rows without mutating the ledger. Current target cells missing from persisted rows SHALL count as `pending`. Current target cells whose persisted digest no longer matches the current digest SHALL count as `stale`. Persisted cells that are no longer part of the current target SHALL remain visible as `superseded` coverage when included in the effective coverage summary. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root. When current review cells are pending, `status` SHALL expose review work as the next required action before exposing live finding work. When pending cells are exhausted but current review cells are stale, `status` SHALL expose live finding work before generic stale review work so fix-driven stale coverage can be handled after finding work. Live finding work SHALL include reopened findings, untriaged findings, confirmed findings, and fixed-pending verification. When the last reviewed target digest differs from the current target digest, `status` SHALL NOT expose review work solely because of that whole-target digest drift if all current target cells are already present, reviewed, and have matching content digests. In that complete-coverage case, `status` SHALL continue normal finding-state priority, including fixed-finding verification.

`review-gauntlet ready` SHALL expose whether a continuation task is available through both stdout and process exit status. When a ready prompt exists, the command SHALL emit the existing prompt output and exit `0`. When no continuation task exists, the command SHALL preserve the existing no-task output while exiting `1` so external orchestrators can distinguish no-op completion without parsing stdout. When current review cells are pending, `ready` SHALL prompt for pending review before prompting for reopened, untriaged, confirmed, fixed-pending, or stale work. When pending cells are exhausted but current review cells are stale, `ready` SHALL prompt for live finding work before prompting for generic stale review work. Live finding work SHALL include reopened findings, untriaged findings, confirmed findings, and fixed-pending verification. After review-cell and finding continuation work is exhausted, `ready` SHALL treat dirty working-tree finalize blockers as actionable by returning a prompt that instructs the agent to commit intended git changes before finalizing. Commit-resolvable dirty blockers include dirty review-universe files relative to `HEAD` and uncommitted non-review files. `ready` SHALL NOT treat non-dirty finalize blockers as commit-resolvable. `ready` SHALL NOT return a target-digest-drift review prompt solely because whole-target digest drift exists when current target-cell coverage is complete.

#### Scenario: Status prioritizes confirmed findings before generic stale review

**Given**: an active review session whose current target has no pending review cells
**And**: at least one current target cell is stale
**And**: at least one finding is `confirmed`
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `coverage.stale` greater than `0`
**And**: `finding_state_counts.confirmed` is greater than `0`
**And**: `next_required_action` is `fix_confirmed_findings`
**And**: the stale coverage remains visible as a finalization blocker

#### Scenario: Status prioritizes fixed verification before generic stale review

**Given**: an active review session whose current target has no pending review cells
**And**: at least one current target cell is stale
**And**: at least one finding is `fixed_pending_verification`
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `coverage.stale` greater than `0`
**And**: `finding_state_counts.fixed_pending_verification` is greater than `0`
**And**: `next_required_action` is `verify_fixes`
**And**: the stale coverage remains visible as a finalization blocker

#### Scenario: Status keeps pending review before finding work

**Given**: an active review session whose current target has at least one pending review cell
**And**: at least one finding is `confirmed` or `fixed_pending_verification`
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `coverage.pending` greater than `0`
**And**: `next_required_action` is `run_review`
**And**: the live finding counts remain visible in `finding_state_counts`

#### Scenario: Ready prioritizes live findings before generic stale review

**Given**: an active review session whose current target has no pending review cells
**And**: at least one current target cell is stale
**And**: at least one finding is `confirmed` or `fixed_pending_verification`
**When**: the developer runs `review-gauntlet ready`
**Then**: stdout prompts for the applicable live finding work
**And**: stdout does not prompt for generic stale review work before that live finding work is exhausted
