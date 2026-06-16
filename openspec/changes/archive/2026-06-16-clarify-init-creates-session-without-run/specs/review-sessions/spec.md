## MODIFIED Requirements

### Requirement: Init SHALL default to latest checkpoint or all-files review

`review-gauntlet init` without explicit target flags SHALL choose a deterministic default target. If a usable latest checkpoint exists, the default target SHALL be the diff from that checkpoint's `review_base_commit` to `HEAD`. If no latest checkpoint exists, the default target SHALL include all eligible repository files. If a latest checkpoint exists but cannot safely be used, `init` SHALL fail explicitly instead of silently falling back. This is a breaking change from the previous bare-`init` worktree default; callers that require worktree review SHALL pass `--worktree` explicitly.

`review-gauntlet init` SHALL create an active review session and review cells, but SHALL NOT start review execution or create a review run. Its output SHALL distinguish the active session lifecycle from the absent review-run lifecycle and SHALL point developers to the command that starts review execution.

<!-- Expected canonical result after archive: the canonical review-sessions spec will make explicit that init creates an active session without creating a review run, and that init output must expose the next review command. -->

#### Scenario: Init defaults to latest checkpoint diff when available

**Given**: `.review-gauntlet/checkpoints/latest/status.json` exists
**And**: the latest checkpoint files share consistent checkpoint metadata
**And**: the checkpoint contains `usable_as_review_base: true`
**And**: the checkpoint contains a `review_base_commit` that resolves to a commit in the current repository
**And**: `review_base_commit` is an ancestor of `HEAD`
**When**: the developer runs `review-gauntlet init --format json` without target flags
**Then**: the initialized session target is equivalent to `--from <review_base_commit> --to HEAD`
**And**: review cells are scoped to files changed between that commit and `HEAD`

#### Scenario: Init defaults to all files when no checkpoint exists

**Given**: `.review-gauntlet/checkpoints/latest/status.json` does not exist
**When**: the developer runs `review-gauntlet init --format json` without target flags
**Then**: the initialized session target is equivalent to `--all`
**And**: review cells are built from all eligible repository files

#### Scenario: Init creates an active session without starting a run

**Given**: a repository with eligible review files
**When**: the developer runs `review-gauntlet init --format json`
**Then**: `.review-gauntlet/active-session.json` records the new active session ID
**And**: the session ledger contains the initialized review cells
**And**: no review run row is created for the session
**And**: stdout includes `session_state: active`, `run_count: 0`, and a lifecycle field showing that no run has started
**And**: stdout identifies `review-gauntlet review` as the next command for starting review execution

#### Scenario: Review creates the first run after init

**Given**: a repository where `review-gauntlet init --format json` has created an active session
**And**: the session has pending review cells
**When**: the developer runs `review-gauntlet review --format json` with a configured adapter or fixture
**Then**: the first review run is created
**And**: the command output reports a non-null `run_id`
**And**: subsequent status output reports `run_count` greater than or equal to `1`

#### Scenario: Init rejects invalid latest checkpoint instead of falling back

**Given**: `.review-gauntlet/checkpoints/latest/status.json` exists
**And**: the checkpoint is malformed, internally inconsistent, has `usable_as_review_base` other than `true`, lacks `review_base_commit`, references a commit that cannot be resolved, or references a commit that is not an ancestor of `HEAD`
**When**: the developer runs `review-gauntlet init --format json` without target flags
**Then**: the command fails with an actionable checkpoint error
**And**: no all-files fallback session is created

#### Scenario: Explicit init target flags override checkpoint default

**Given**: `.review-gauntlet/checkpoints/latest/status.json` exists and is usable
**When**: the developer runs `review-gauntlet init --all`, `review-gauntlet init --worktree`, `review-gauntlet init --from main --to HEAD`, or `review-gauntlet init --commit <commit>`
**Then**: the explicit target mode is used
**And**: the latest checkpoint does not override that explicit target selection
