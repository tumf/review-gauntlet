## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

`findings --path` filters SHALL accept only repository-relative paths and directory prefixes. Absolute paths and parent-directory traversal SHALL fail with a usage error so filtering semantics remain repository-scoped and deterministic.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root. When current review cells are pending or stale, `status` SHALL expose review work as the next required action before exposing live finding work, including confirmed finding work. When the last reviewed target digest differs from the current target digest, `status` SHALL expose review work as the next required action without requiring `status` to mutate persisted review cell states.

`review-gauntlet ready` SHALL expose whether a continuation task is available through both stdout and process exit status. When a ready prompt exists, the command SHALL emit the existing prompt output and exit `0`. When no continuation task exists, the command SHALL preserve the existing no-task output while exiting `1` so external orchestrators can distinguish no-op completion without parsing stdout. When current review cells are pending or stale, `ready` SHALL prompt for review coverage before prompting for reopened, untriaged, confirmed, or fixed-pending finding work. After review-cell and finding continuation work is exhausted, `ready` SHALL treat dirty working-tree finalize blockers as actionable by returning a prompt that instructs the agent to commit intended git changes before finalizing. Commit-resolvable dirty blockers include dirty review-universe files relative to `HEAD` and uncommitted non-review files. `ready` SHALL NOT treat non-dirty finalize blockers as commit-resolvable. `ready` SHALL also treat target digest drift since the last review run as actionable review work, returning a review-oriented prompt without mutating session ledger state.

#### Scenario: Status maps pending coverage ahead of confirmed findings

**Given**: an active review session with pending review cells
**And**: the session has confirmed findings
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `next_required_action` equal to `run_review`
**And**: stdout contains finalize blockers for both pending review cells and confirmed findings
**And**: the command does not mutate persisted review cell or finding state

#### Scenario: Status maps stale coverage ahead of confirmed findings

**Given**: an active review session with stale review cells
**And**: the session has confirmed findings
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `next_required_action` equal to `run_review`
**And**: stdout contains finalize blockers for both stale review cells and confirmed findings
**And**: the command does not mutate persisted review cell or finding state

#### Scenario: Ready prompts review ahead of confirmed finding fixes

**Given**: an active review session with pending or stale review cells
**And**: the session has confirmed findings
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON with a string `prompt`
**And**: the prompt instructs the agent to review pending or stale review cells
**And**: the prompt does not instruct the agent to fix confirmed findings before coverage is complete
**And**: no checkpoint is written
**And**: no ledger state is modified
