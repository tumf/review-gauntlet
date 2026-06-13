## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

`findings --path` filters SHALL accept only repository-relative paths and directory prefixes. Absolute paths and parent-directory traversal SHALL fail with a usage error so filtering semantics remain repository-scoped and deterministic.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root. When current review cells are pending or stale, `status` SHALL expose review work as the next required action before exposing live finding work. When the last reviewed target digest differs from the current target digest, `status` SHALL expose review work as the next required action without requiring `status` to mutate persisted review cell states.

`review-gauntlet ready` SHALL expose whether a continuation task is available through both stdout and process exit status. When a ready prompt exists, the command SHALL emit the existing prompt output and exit `0`. When no continuation task exists, the command SHALL preserve the existing no-task output while exiting `1` so external orchestrators can distinguish no-op completion without parsing stdout. When current review cells are pending or stale, `ready` SHALL prompt for review coverage before prompting for reopened, untriaged, confirmed, or fixed-pending finding work. After review-cell and finding continuation work is exhausted, `ready` SHALL treat dirty working-tree finalize blockers as actionable by returning a prompt that instructs the agent to commit intended git changes before finalizing. Commit-resolvable dirty blockers include dirty review-universe files relative to `HEAD` and uncommitted non-review files. `ready` SHALL NOT treat non-dirty finalize blockers as commit-resolvable. `ready` SHALL also treat target digest drift since the last review run as actionable review work, returning a review-oriented prompt without mutating session ledger state.

#### Scenario: Findings mark filter matches hyphenated public state

**Given**: an active session with a `false_positive` finding
**When**: the developer runs `review-gauntlet findings --all --mark false-positive --format json`
**Then**: stdout contains parseable JSON whose `findings` list includes that false-positive finding

#### Scenario: Findings path filter rejects traversal

**Given**: an active session
**When**: the developer runs `review-gauntlet findings --path ../src`
**Then**: the command fails with a usage error
**And**: no finding state is modified

#### Scenario: Status works with default root

**Given**: an active review session in the current repository
**When**: the developer runs `review-gauntlet status --format json` from the repository root
**Then**: stdout contains parseable JSON session status
**And**: target digest computation does not fail due to relative and absolute path mixing

#### Scenario: Status maps incomplete coverage ahead of finding work

**Given**: an active review session with pending review cells
**And**: the session has untriaged findings
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `next_required_action` equal to `run_review`
**And**: stdout contains finalize blockers for both pending review cells and untriaged findings
**And**: the command does not mutate persisted review cell or finding state

#### Scenario: Ready prompts review ahead of finding work

**Given**: an active review session with pending review cells
**And**: the session has untriaged findings
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON with a string `prompt`
**And**: the prompt instructs the agent to review pending review cells
**And**: the prompt does not instruct the agent to triage findings before coverage is complete
**And**: no checkpoint is written
**And**: no ledger state is modified

#### Scenario: Status maps target digest drift to review work

**Given**: an active review session whose persisted review cells are not stale
**And**: the last reviewed target digest differs from the current target digest
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `next_required_action` equal to `run_review`
**And**: the command does not mutate persisted review cell states

#### Scenario: Ready exits zero when an actionable task exists

**Given**: an active review session with at least one pending continuation task
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON with a string `prompt`
**And**: the command exits `0`

#### Scenario: Ready exits non-zero when no continuation task exists

**Given**: an active review session where `ready` has no continuation task to return
**When**: the developer runs `review-gauntlet ready --format text`
**Then**: stdout is `no ready task`
**And**: the command exits `1`

#### Scenario: Ready JSON preserves null prompt when no continuation task exists

**Given**: an active review session where `ready` has no continuation task to return
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON with `prompt` equal to `null`
**And**: the command exits `1`

#### Scenario: Ready prompts commit before finalize for dirty git blockers

**Given**: an active review session whose review cells are all reviewed
**And**: all findings are terminal
**And**: finalization is blocked only by dirty review-universe files and/or uncommitted non-review files
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON with a string `prompt`
**And**: the prompt instructs the agent to commit intended git changes before finalizing
**And**: the command exits `0`
**And**: no checkpoint is written
**And**: no ledger state is modified

#### Scenario: Ready prompts review for target digest drift without mutating state

**Given**: an active review session whose persisted review cells are not stale
**And**: all findings are terminal
**And**: finalization is blocked by target digest drift since the last review run
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON with a string `prompt`
**And**: the prompt instructs the agent to run review work
**And**: the command exits `0`
**And**: no checkpoint is written
**And**: no ledger state is modified

#### Scenario: Ready preserves no-task behavior for non-commit non-drift finalize blockers

**Given**: an active review session whose review cells and findings have no pending continuation work
**And**: finalization is blocked by at least one blocker that committing dirty files cannot resolve
**And**: finalization is not blocked by target digest drift
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON with `prompt` equal to `null`
**And**: the command exits `1`
