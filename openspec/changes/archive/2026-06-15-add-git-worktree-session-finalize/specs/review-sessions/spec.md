## ADDED Requirements

### Requirement: Git worktree sessions SHALL isolate review work by session

`review-gauntlet init --git-worktree` SHALL create a Git-worktree-backed review session without changing existing target-selection semantics. The existing `init --worktree` flag SHALL continue to mean workspace-diff target selection. `--git-worktree` SHALL be composable with existing target modes, including `--worktree`.

A Git-worktree-backed session SHALL record enough durable metadata to later verify and finalize the session branch: base branch, base commit, session branch, worktree path, and whether Git worktree mode is enabled. Branch names and worktree paths SHALL be generated from path-safe session identifiers and scoped to Review Gauntlet-owned namespaces by default.

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

### Requirement: Finalize merge SHALL merge and clean up Git worktree sessions

`review-gauntlet finalize --merge` SHALL be the completion path for Git-worktree-backed sessions. It SHALL first enforce all normal finalization blockers. When those blockers are absent, it SHALL write checkpoint artifacts, commit intended session branch changes including checkpoint artifacts, merge the session branch into the recorded base branch, finalize the session, clear the active session marker, remove the linked session worktree, and delete the session branch.

`finalize --merge` SHALL produce structured output that distinguishes checkpoint success, merge success, and cleanup success. Merge blockers SHALL leave the active session, session branch, and session worktree available for repair. Cleanup failures after a successful merge SHALL NOT pretend the merge failed, but SHALL report cleanup blockers and a follow-up cleanup action.

#### Scenario: Finalize merge completes checkpoint, merge, and cleanup

**Given**: an active Git-worktree-backed review session with complete reviewed coverage and all live findings closed
**And**: review-universe files are clean relative to session branch `HEAD`
**And**: the recorded base branch exists, is clean, and still points at the recorded base commit
**When**: the developer runs `review-gauntlet finalize --merge --format json`
**Then**: checkpoint artifacts are written for the session
**And**: the checkpoint artifacts and intended session changes are committed on the session branch
**And**: the session branch is merged into the recorded base branch
**And**: the result includes `merged: true`, the recorded base branch, the session branch, and the resulting merge commit
**And**: the active session marker is removed or invalidated
**And**: the linked session worktree is removed
**And**: the session branch is deleted
**And**: the result includes `cleaned_up: true` with removed worktree and deleted branch evidence

#### Scenario: Finalize merge rejects non Git-worktree sessions

**Given**: an active review session that was not created with `--git-worktree`
**When**: the developer runs `review-gauntlet finalize --merge --format json`
**Then**: the command fails with a structured blocker explaining that merge finalization requires a Git-worktree-backed session
**And**: no checkpoint file is created solely because `--merge` was requested
**And**: no branch merge or cleanup is attempted
**And**: the active session marker remains usable for continuing review work

#### Scenario: Merge blockers preserve repairable session state

**Given**: an active Git-worktree-backed review session that otherwise satisfies normal finalization requirements
**And**: the recorded base branch is missing, dirty, advanced beyond the recorded base commit, the session branch is missing, the session worktree is missing, or the session branch cannot merge cleanly
**When**: the developer runs `review-gauntlet finalize --merge --format json`
**Then**: the command fails with structured merge blockers
**And**: the result includes `merged: false`
**And**: no cleanup of the session branch or session worktree is performed
**And**: the active session marker remains usable for continuing or repairing the session

#### Scenario: Cleanup failure after merge is reported without hiding merge success

**Given**: an active Git-worktree-backed review session eligible for `finalize --merge`
**And**: the session branch is successfully merged into the recorded base branch
**And**: removing the session worktree or deleting the session branch fails
**When**: `review-gauntlet finalize --merge --format json` returns
**Then**: the result includes `merged: true`
**And**: the result includes `cleaned_up: false`
**And**: the result includes cleanup blocker evidence
**And**: the result includes `next_required_action: cleanup_git_worktree`
**And**: the session is recorded as finalized rather than active

### Requirement: CLI documentation SHALL distinguish target worktree from Git worktree isolation

Review Gauntlet CLI help and documentation SHALL distinguish `init --worktree` as workspace-diff target selection from `init --git-worktree` as Git linked worktree session isolation. Documentation SHALL describe `finalize --merge` as the operation that merges and cleans up Git-worktree-backed sessions.

#### Scenario: Help exposes both worktree concepts without ambiguity

**Given**: an installed or development invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet init --help`
**Then**: help text describes `--worktree` as reviewing workspace changes
**And**: help text describes `--git-worktree` as creating an isolated Git worktree and session branch

#### Scenario: Documentation shows merge cleanup workflow

**Given**: a developer reads repository usage documentation
**When**: they follow the Git-worktree-backed session workflow
**Then**: the documentation shows `review-gauntlet init --git-worktree`
**And**: the documentation shows `review-gauntlet finalize --merge`
**And**: the documentation explains that successful merge finalization removes the session worktree and deletes the session branch
