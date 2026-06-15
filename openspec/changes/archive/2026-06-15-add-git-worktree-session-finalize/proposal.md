---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - openspec/specs/developer-workflow/spec.md
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/checkpoint.py
  - src/review_gauntlet/session_store.py
  - src/review_gauntlet/targets.py
---

# Add Git worktree session finalize workflow

**Change Type**: implementation

## Premise / Context

- Review Gauntlet already has a `--worktree` target mode meaning staged, unstaged, and untracked workspace-diff review; this proposal must not redefine that flag.
- Review sessions persist durable ledger metadata in `.review-gauntlet/ledger.sqlite`, and `finalize` currently writes checkpoint artifacts then clears the active session marker.
- The current `finalize` gate requires complete coverage, closed live findings, clean review-universe files relative to `HEAD`, and a resolvable current commit before writing checkpoint files.
- The user wants an opt-in Git linked worktree workflow: `init --git-worktree`, then `finalize --merge` that merges and cleans up the session worktree and branch.
- The Constitution requires coverage truth and incomplete states to remain explicit; merge and cleanup must not hide unfinished review, dirty state, or failed verification.

## Problem / Context

Developers want each review-gauntlet session to run in an isolated Git branch and linked worktree so review work, fixes, checkpoint artifacts, and agent changes do not collide with the original checkout. After review completion, developers want one command to finalize, merge the session branch back into the original branch, and remove the temporary worktree and branch.

The existing workflow does not manage Git branches or linked worktrees. It also leaves checkpoint artifacts to be committed manually after `finalize`, which is incompatible with a `finalize --merge` operation that must have committed content to merge.

## Proposed Solution

Add an opt-in Git worktree session workflow:

1. `review-gauntlet init --git-worktree` creates a session branch and linked Git worktree for the session while preserving the existing target-selection behavior.
2. Existing `review-gauntlet init --worktree` remains the workspace-diff review-target flag. It may be combined with `--git-worktree`.
3. Session metadata records the base branch, base commit, session branch, worktree path, and cleanup/merge policy information.
4. `review-gauntlet finalize --merge` finalizes a Git-worktree-backed session by writing checkpoint artifacts, committing intended session changes including checkpoint artifacts on the session branch, merging the session branch into the recorded base branch, then removing the session worktree and deleting the session branch.
5. Merge and cleanup behavior is structured and auditable in JSON/text output. Merge blockers leave the session branch and worktree intact. Cleanup failure after a successful merge keeps the session finalized but reports cleanup evidence and a follow-up action.

## Acceptance Criteria

- `init --git-worktree` creates a unique session branch and linked worktree, stores Git-worktree metadata in the session ledger, and returns the branch/worktree evidence in JSON output.
- `init --worktree` continues to mean workspace-diff review target, and `init --worktree --git-worktree` combines workspace-diff targeting with Git worktree isolation.
- Session worktree paths and branch names are deterministic, path-safe, collision-resistant, and scoped under `.review-gauntlet/worktrees/` and a `review-gauntlet/` branch namespace by default.
- `finalize --merge` is accepted by the CLI and only performs merge behavior for sessions created with `--git-worktree`.
- `finalize --merge` preserves all existing finalization blockers before writing checkpoint files or attempting merge.
- `finalize --merge` commits checkpoint artifacts and intended session branch changes before merging.
- `finalize --merge` blocks with structured output when the recorded base branch has advanced, is dirty, is missing, the session branch/worktree is missing, or merge would conflict.
- Successful `finalize --merge` merges the session branch into the recorded base branch, finalizes the session, clears the active session marker, removes the session worktree, deletes the session branch, and returns merge plus cleanup evidence.
- If merge succeeds but cleanup fails, the session remains finalized and merged, the command reports `cleaned_up: false`, includes cleanup blockers, and returns a follow-up action instead of pretending cleanup succeeded.
- Documentation and help text make clear that `--worktree` is target selection while `--git-worktree` is Git worktree isolation.

## Explicit Completion Conditions

- Parser help and completion-visible options include `init --git-worktree` and `finalize --merge` without changing existing `--worktree` semantics.
- `src/review_gauntlet` contains tested Git helper logic for session branch/worktree creation, merge preflight, merge execution, and cleanup.
- Session metadata and command output include sufficient fields for a reviewer to trace base branch, base commit, session branch, worktree path, merge commit, cleanup status, and blockers.
- Unit and integration tests exercise success, compatibility, blocker, and cleanup-failure paths using local temporary Git repositories.
- `make check` passes after implementation.

## Out of Scope

- Changing the meaning of existing `init --worktree`.
- Supporting remote push, pull request creation, or hosted Git provider integration.
- Automatically rebasing or resolving base-branch advancement; the first implementation should block and report the required action.
- Deleting user-created non-session branches or worktrees outside the recorded session metadata.
- Long-running background orchestration beyond the existing `run` command behavior.
