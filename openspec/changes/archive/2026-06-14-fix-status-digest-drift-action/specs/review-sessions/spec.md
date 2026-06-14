## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

`findings --path` filters SHALL accept only repository-relative paths and directory prefixes. Absolute paths and parent-directory traversal SHALL fail with a usage error so filtering semantics remain repository-scoped and deterministic.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root. When current review cells are pending, stale, or missing from the session ledger, `status` SHALL expose review work as the next required action before exposing live finding work, including confirmed finding work and fixed-finding verification work. When the last reviewed target digest differs from the current target digest, `status` SHALL NOT expose review work solely because of that whole-target digest drift if all current target cells are already present, reviewed, and have matching content digests. In that complete-coverage case, `status` SHALL continue normal finding-state priority, including fixed-finding verification.

`review-gauntlet ready` SHALL expose whether a continuation task is available through both stdout and process exit status. When a ready prompt exists, the command SHALL emit the existing prompt output and exit `0`. When no continuation task exists, the command SHALL preserve the existing no-task output while exiting `1` so external orchestrators can distinguish no-op completion without parsing stdout. When current review cells are pending, stale, or missing from the session ledger, `ready` SHALL prompt for review coverage before prompting for reopened, untriaged, confirmed, or fixed-pending finding work. After review-cell and finding continuation work is exhausted, `ready` SHALL treat dirty working-tree finalize blockers as actionable by returning a prompt that instructs the agent to commit intended git changes before finalizing. Commit-resolvable dirty blockers include dirty review-universe files relative to `HEAD` and uncommitted non-review files. `ready` SHALL NOT treat non-dirty finalize blockers as commit-resolvable. `ready` SHALL NOT return a target-digest-drift review prompt solely because whole-target digest drift exists when current target-cell coverage is complete.

#### Scenario: Status maps target digest drift with incomplete current coverage to review work

**Given**: an active review session whose current target includes a pending, stale, or missing review cell
**And**: the last reviewed target digest differs from the current target digest
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `next_required_action` equal to `run_review`
**And**: the command does not mutate persisted review cell states

#### Scenario: Status maps complete coverage with fixed-pending findings to verification despite digest drift

**Given**: an active review session whose current target cells are all present in the ledger
**And**: all current target cells are `reviewed` with matching content digests
**And**: the session has findings in `fixed_pending_verification`
**And**: the last reviewed target digest differs from the current target digest only at the whole-target freshness layer
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `next_required_action` equal to `run_verify_fixes`
**And**: stdout still reports that fixed findings require verification
**And**: the command does not mutate persisted review cell or finding state

#### Scenario: Ready prompts verification when coverage is complete despite digest drift

**Given**: an active review session whose current target cells are all `reviewed` with matching content digests
**And**: the session has findings in `fixed_pending_verification`
**And**: the last reviewed target digest differs from the current target digest only at the whole-target freshness layer
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON with a string `prompt`
**And**: the prompt instructs the agent to verify fixed-pending findings
**And**: the prompt does not instruct the agent to review target digest drift
**And**: no persisted review cell or finding state is modified
