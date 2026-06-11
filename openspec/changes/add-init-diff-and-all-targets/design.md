# Design: Init target scopes

## Premise / Context

The project constitution requires `review-gauntlet review` to advance the active session exactly once. Target selection therefore remains an initialization concern, not a review-run concern.

## Target scope model

The implementation should separate two concepts that are currently easy to conflate:

1. Target policy metadata: what the session is meant to track over time.
2. Review-universe file discovery: which repository files become review cells for that target.

The proposed target scopes are:

- Workspace diff: moving target; changed working tree files plus untracked non-ignored files.
- Branch diff: moving target; eligible files changed between base and head refs.
- Commit diff: fixed target; eligible files changed by one commit.
- Full repository: moving target; all eligible project files from the existing inventory rules.

## Command surface

`review-gauntlet init` should be the OCR-compatible workspace diff default. `--worktree` remains accepted as a compatibility alias. `--all` is explicit because full-repository review is more expensive and broader than OCR review.

`review-gauntlet review` should remain target-option-free so an active session's coverage ledger cannot be silently retargeted during a run.

## File discovery approach

Diff modes should obtain candidate relative paths through bounded git subprocesses and then apply the same built-in path exclusions used by inventory. File candidates that no longer exist in the working tree should not create current review cells. Untracked files should be included only in workspace diff mode.

Full-repository mode should continue to use the existing inventory path so current behavior remains available under an explicit name.

## Verification strategy

Use temporary git repositories in tests to verify actual command behavior instead of mocking all git output. Tests should cover changed and unchanged tracked files, staged changes, unstaged changes, untracked files, ignored files, branch comparisons, commit comparisons, and full repository mode.
