## MODIFIED Requirements

### Requirement: Git worktree sessions SHALL isolate review work by session

`review-gauntlet init --git-worktree` SHALL create a Git-worktree-backed review session without changing existing target-selection semantics. The existing `init --worktree` flag SHALL continue to mean workspace-diff target selection. `--git-worktree` SHALL be composable with existing target modes, including `--worktree`.

A Git-worktree-backed session SHALL record enough durable metadata to later verify and finalize the session branch: base branch, base commit, session branch, worktree path, and whether Git worktree mode is enabled. Branch names and worktree paths SHALL be generated from path-safe session identifiers and scoped to Review Gauntlet-owned namespaces by default.

For Git-worktree-backed `review-gauntlet run` sessions, external command adapter steps SHALL use the linked session worktree as the agent-facing repository root while preserving the base repository `.review-gauntlet` directory as the durable review state and artifact location.

#### Scenario: Init creates a session branch and linked worktree

**Given**: a developer is in a Git repository on branch `main` with a resolvable `HEAD`
**When**: they run `review-gauntlet init --git-worktree --format json`
**Then**: a unique session branch under a Review Gauntlet-owned branch namespace is created
**And**: a linked Git worktree for that session branch is created under a Review Gauntlet-owned worktree directory
**And**: the session metadata records `git_worktree.enabled: true`, `base_branch`, `base_commit`, `session_branch`, and `worktree_path`
**And**: stdout includes the session branch and worktree path evidence

#### Scenario: Existing worktree target semantics are preserved

**Given**: a repository with staged, unstaged, or untracked workspace changes
**When**: the developer runs `review-gauntlet init --worktree --format json`
**Then**: Review Gauntlet selects the workspace-diff review target as before
**And**: no Git linked worktree is created solely because `--worktree` was provided

#### Scenario: Workspace-diff targeting composes with Git worktree isolation

**Given**: a repository with staged, unstaged, or untracked workspace changes
**When**: the developer runs `review-gauntlet init --worktree --git-worktree --format json`
**Then**: the review target is the workspace-diff target
**And**: a session branch and linked Git worktree are created for the session
**And**: the session metadata records both the workspace-diff target and Git-worktree session metadata

#### Scenario: Run executes the agent inside the linked session worktree

**Given**: an active session created with `review-gauntlet init --git-worktree`
**And**: the configured command adapter has no explicit `cwd`
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the external command adapter is invoked with cwd equal to the linked session worktree root
**And**: source file reads and edits performed by the adapter target the session branch worktree rather than the base worktree
**And**: command stdout, stderr, activity artifacts, and session ledger state remain under the base repository `.review-gauntlet` directory

#### Scenario: Run templates distinguish agent root from state directory

**Given**: an active session created with `review-gauntlet init --git-worktree`
**And**: the configured command adapter uses `{repo_root}` and `{state_dir}` templates
**When**: the developer runs `review-gauntlet run --format json`
**Then**: `{repo_root}` expands to the linked session worktree root
**And**: `{state_dir}` expands to the base repository `.review-gauntlet` state directory
**And**: the two paths are not collapsed to the same directory solely because Git worktree mode is enabled

#### Scenario: Adapter cwd is constrained inside the session worktree

**Given**: an active session created with `review-gauntlet init --git-worktree`
**And**: the configured command adapter declares a relative `cwd`
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the relative cwd is resolved from the linked session worktree root
**And**: the command fails before adapter execution if the resolved cwd escapes the linked session worktree

#### Scenario: Non Git-worktree run keeps existing command root behavior

**Given**: an active session that was not created with `--git-worktree`
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the external command adapter uses the base repository root as the agent-facing root
**And**: `{repo_root}` continues to expand to the base repository root
**And**: configured adapter cwd remains constrained inside the base repository root
