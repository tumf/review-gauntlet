## MODIFIED Requirements

### Requirement: Review sessions SHALL persist durable state

`review-gauntlet` SHALL support durable review sessions stored under `.review-gauntlet/` at the reviewed repository root. A session SHALL preserve the target policy, active session metadata, ruleset identity, review universe state, immutable run history, review cells, findings, finding occurrences, and finding events. Target policy selection SHALL occur during `init`, not during `review`. The default `init` target SHALL be OCR-compatible workspace diff review; full-repository review SHALL require explicit `--all`.

#### Scenario: Initialize the default workspace diff review session

**Given**: a Git repository with staged changes, unstaged changes, untracked non-ignored files, and unrelated unchanged tracked files
**When**: the developer runs `review-gauntlet init`
**Then**: the CLI creates durable session state under `.review-gauntlet/`
**And**: records a moving workspace diff target policy
**And**: creates initial review cells only for eligible staged, unstaged, and untracked non-ignored files
**And**: does not create review cells for unrelated unchanged tracked files
**And**: does not execute a review run

#### Scenario: Initialize an explicit worktree review session

**Given**: a Git repository with staged changes, unstaged changes, and untracked non-ignored files
**When**: the developer runs `review-gauntlet init --worktree`
**Then**: the CLI creates the same workspace diff target policy as default `review-gauntlet init`
**And**: records enough target information for later review runs to detect changed workspace diff content

#### Scenario: Initialize a branch review session

**Given**: a repository with a valid base reference and head reference
**And**: the head reference changes some eligible files while other tracked files remain unchanged
**When**: the developer runs `review-gauntlet init --from origin/main --to HEAD`
**Then**: the CLI creates durable session state under `.review-gauntlet/`
**And**: records the base reference, head reference, moving head mode, target kind, ruleset digest, and initial review cells
**And**: creates review cells for eligible files changed between the base and head references
**And**: does not create review cells for unrelated unchanged tracked files
**And**: does not execute a review run

#### Scenario: Initialize a fixed commit review session

**Given**: a repository with a valid commit object that changes eligible files
**When**: the developer runs `review-gauntlet init --commit abc123`
**Then**: the CLI creates a fixed-target session for that commit
**And**: creates review cells for eligible files changed by that commit
**And**: later runs treat the target as immutable unless a new session is initialized

#### Scenario: Initialize a full repository review session

**Given**: a repository with eligible tracked files, eligible untracked non-ignored files, ignored files, and review-gauntlet generated state
**When**: the developer runs `review-gauntlet init --all`
**Then**: the CLI creates a full-repository targeted session
**And**: creates review cells from the existing full inventory rules
**And**: excludes ignored files, built-in generated artifacts, and `.review-gauntlet/` state
**And**: does not execute a review run

#### Scenario: Init rejects mixed target scopes

**Given**: a repository
**When**: the developer combines `--all` with `--worktree`, `--commit`, or `--from/--to`
**Then**: the CLI fails with a usage error
**And**: no new review session is created

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL advance the active session by one review run only. It SHALL recalculate the current review universe according to the active session's target policy, reconcile existing ledger state, review eligible cells within the configured budget, execute review work through the selected review adapter, update cell coverage only for successfully reviewed cells, record findings and occurrences, verify pending fixes when possible, and return the next required action without recursively continuing the session loop. It SHALL NOT accept target selection flags or retarget the active session.

#### Scenario: Review advances once with remaining pending work

**Given**: an active session with more pending review cells than the current review budget
**When**: the developer runs `review-gauntlet review`
**Then**: the CLI creates exactly one immutable run record
**And**: reviews only the cells selected for that run
**And**: leaves remaining eligible cells pending
**And**: reports that the next required action is to run review again or triage findings, depending on the run result

#### Scenario: Review rejects target selection flags

**Given**: an active session
**When**: the developer runs `review-gauntlet review --from main --to HEAD`, `review-gauntlet review --commit abc123`, `review-gauntlet review --worktree`, or `review-gauntlet review --all`
**Then**: argument parsing fails with a usage error
**And**: the active session target policy is not changed
**And**: no review run is created
