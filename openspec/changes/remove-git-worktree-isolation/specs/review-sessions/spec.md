## REMOVED Requirements

### Requirement: Git worktree sessions SHALL isolate review work by session

**Reason**: Review Gauntlet shall not create, remove, merge, or otherwise operate Git linked worktrees. The `--git-worktree` feature is removed entirely. `--worktree` remains only workspace-diff target selection.

### Requirement: Finalize merge SHALL merge and clean up Git worktree sessions

**Reason**: `finalize --merge` is a Git-worktree-only completion path. With Git linked worktree operations removed, the `--merge` flag and its entire merge/cleanup lifecycle are no longer supported.

### Requirement: CLI documentation SHALL distinguish target worktree from Git worktree isolation

**Reason**: With `--git-worktree` removed, the only remaining `--worktree` flag means workspace-diff target selection. No documentation distinction is needed beyond the existing help text for `--worktree`.

## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

Review Gauntlet SHALL NOT create, remove, merge, or otherwise operate Git linked worktrees. `review-gauntlet finalize` closes a complete active review session into deterministic latest-only checkpoint files; the removed `--merge` flag no longer exists. The checkpoint-only git commit in the run workflow continues to guard against unrelated dirty worktree changes (files outside `.review-gauntlet` that are dirty relative to `HEAD`), but the term "dirty worktree" here refers to uncommitted files in the base repository working directory, not a Git linked worktree.

#### Scenario: Finalize does not expose a merge flag

**Given**: an installed `review-gauntlet` CLI
**When**: the developer runs `review-gauntlet finalize --merge`
**Then**: the command exits with a usage error (exit code 64)
**And**: the error message does not suggest `--merge` as a valid option
**And**: no checkpoint files, branch merges, or worktree cleanup are attempted

#### Scenario: Stale git_worktree metadata does not affect run

**Given**: an active session whose metadata contains `git_worktree.enabled: true` and a `worktree_path` from a pre-removal session
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the agent is invoked with `{repo_root}` expanding to the base repository root
**And**: the default agent cwd is the base repository root
**And**: no `worktree_error` is raised
**And**: the run proceeds or blocks normally based on the current session state

## ADDED Requirements

### Requirement: Review Gauntlet SHALL NOT operate Git linked worktrees

Review Gauntlet SHALL NOT create, remove, merge, or otherwise mutate Git linked worktrees as part of its session lifecycle. The CLI SHALL NOT accept `--git-worktree`, `--no-setup`, or `--merge` flags. `--worktree` remains exclusively a target-selection flag meaning "review the workspace diff".

Session metadata and agent execution SHALL NOT interpret any `git_worktree` metadata key. If stale `git_worktree` metadata exists from a pre-removal session, Review Gauntlet SHALL proceed using the base repository root and SHALL NOT trigger any linked-worktree behavior.

#### Scenario: Init without --git-worktree records no worktree metadata

**Given**: a developer in a Git repository
**When**: they run `review-gauntlet init --all --format json`
**Then**: the JSON output does not include a `git_worktree` key
**And**: the persisted session metadata does not include a `git_worktree` key

#### Scenario: Init rejects unknown --git-worktree flag

**Given**: a developer in a Git repository
**When**: they run `review-gauntlet init --git-worktree`
**Then**: the command exits with usage error (exit code 64)

#### Scenario: Finalize rejects unknown --merge flag

**Given**: a developer in a Git repository
**When**: they run `review-gauntlet finalize --merge`
**Then**: the command exits with usage error (exit code 64)

#### Scenario: Run ignores stale git_worktree metadata

**Given**: an active session whose metadata was created before `--git-worktree` removal and contains `git_worktree.enabled: true` with a `worktree_path`
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the agent execution root is the base repository root
**And**: no attempt is made to resolve or validate a linked worktree path
**And**: no `worktree_error` reason is emitted
