## MODIFIED Requirements

### Requirement: Review sessions SHALL persist durable state

`review-gauntlet` SHALL support durable review sessions stored under `.review-gauntlet/` at the reviewed repository root. A session SHALL preserve the target policy, active session metadata, ruleset identity, review universe state, immutable run history, review cells, findings, finding occurrences, and finding events. Target policy selection SHALL occur during `init`, not during `review`. The default `init` target SHALL be OCR-compatible workspace diff review; full-repository review SHALL require explicit `--all`. Review universe construction SHALL apply deterministic built-in artifact exclusions and default review-path exclusions, including `openspec/`, `tests/`, and `docs/`, before creating review cells.

#### Scenario: Initialize the default workspace diff review session

**Given**: a Git repository with staged changes, unstaged changes, untracked non-ignored files, and unrelated unchanged tracked files
**When**: the developer runs `review-gauntlet init`
**Then**: the CLI creates durable session state under `.review-gauntlet/`
**And**: records a moving workspace diff target policy
**And**: creates initial review cells only for eligible staged, unstaged, and untracked non-ignored files
**And**: does not create review cells for unrelated unchanged tracked files
**And**: does not create review cells for built-in artifact-excluded paths or default review-path-excluded `openspec/`, `tests/`, `docs/`, test, or generated paths
**And**: does not execute a review run

#### Scenario: Initialize an explicit worktree review session

**Given**: a Git repository with staged changes, unstaged changes, and untracked non-ignored files
**When**: the developer runs `review-gauntlet init --worktree`
**Then**: the CLI creates the same workspace diff target policy as default `review-gauntlet init`
**And**: records enough target information for later review runs to detect changed workspace diff content
**And**: applies the same built-in artifact and default review-path exclusions as default workspace diff initialization

#### Scenario: Initialize a branch review session

**Given**: a repository with a valid base reference and head reference
**And**: the head reference changes some eligible files while other tracked files remain unchanged
**When**: the developer runs `review-gauntlet init --from origin/main --to HEAD`
**Then**: the CLI creates durable session state under `.review-gauntlet/`
**And**: records the base reference, head reference, moving head mode, target kind, ruleset digest, and initial review cells
**And**: creates review cells for eligible files changed between the base and head references
**And**: does not create review cells for unrelated unchanged tracked files
**And**: does not create review cells for built-in artifact-excluded paths or default review-path-excluded `openspec/`, `tests/`, `docs/`, test, or generated paths
**And**: does not execute a review run

#### Scenario: Initialize a fixed commit review session

**Given**: a repository with a valid commit object that changes eligible files
**When**: the developer runs `review-gauntlet init --commit abc123`
**Then**: the CLI creates a fixed-target session for that commit
**And**: creates review cells for eligible files changed by that commit
**And**: does not create review cells for built-in artifact-excluded paths or default review-path-excluded `openspec/`, `tests/`, `docs/`, test, or generated paths changed by that commit
**And**: later runs treat the target as immutable unless a new session is initialized

#### Scenario: Initialize a full repository review session

**Given**: a repository with eligible tracked files, eligible untracked non-ignored files, ignored files, review-gauntlet generated state, generated dependency directories, `openspec/`, `tests/`, `docs/`, and conventional test files
**When**: the developer runs `review-gauntlet init --all`
**Then**: the CLI creates a full-repository targeted session
**And**: creates review cells from the existing full inventory rules
**And**: excludes ignored files, built-in generated artifacts, dependency/vendor directories, and `.review-gauntlet/` state
**And**: excludes default review-path `openspec/`, `tests/`, `docs/`, test, and generated patterns from review cells
**And**: does not execute a review run

#### Scenario: Init rejects mixed target scopes

**Given**: a repository
**When**: the developer combines `--all` with `--worktree`, `--commit`, or `--from/--to`
**Then**: the CLI fails with a usage error
**And**: no new review session is created

#### Scenario: Review universe digest ignores excluded paths

**Given**: an active review session whose target contains eligible source files and built-in excluded generated, `openspec/`, `tests/`, `docs/`, or test paths
**When**: an excluded path changes but eligible source files and review rules do not change
**Then**: the review target digest remains stable for coverage reconciliation
**And**: previously reviewed eligible cells are not marked stale only because of the excluded path change

#### Scenario: Eligible source changes still stale review coverage

**Given**: an active review session with reviewed coverage for an eligible source file
**When**: that eligible source file changes
**Then**: the review target digest changes
**And**: affected review cells become stale according to existing reconciliation behavior
