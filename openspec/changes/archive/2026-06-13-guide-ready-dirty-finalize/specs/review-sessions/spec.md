## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

`findings --path` filters SHALL accept only repository-relative paths and directory prefixes. Absolute paths and parent-directory traversal SHALL fail with a usage error so filtering semantics remain repository-scoped and deterministic.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root.

`review-gauntlet ready` SHALL expose whether a continuation task is available through both stdout and process exit status. When a ready prompt exists, the command SHALL emit the existing prompt output and exit `0`. When no continuation task exists, the command SHALL preserve the existing no-task output while exiting `1` so external orchestrators can distinguish no-op completion without parsing stdout. After review-cell and finding continuation work is exhausted, `ready` SHALL treat dirty working-tree finalize blockers as actionable by returning a prompt that instructs the agent to commit intended git changes before finalizing. Commit-resolvable dirty blockers include dirty review-universe files relative to `HEAD` and uncommitted non-review files. `ready` SHALL NOT treat non-dirty finalize blockers as commit-resolvable.

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

#### Scenario: Ready preserves no-task behavior for non-commit finalize blockers

**Given**: an active review session whose review cells and findings have no pending continuation work
**And**: finalization is blocked by at least one blocker that committing dirty files cannot resolve
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON with `prompt` equal to `null`
**And**: the command exits `1`
