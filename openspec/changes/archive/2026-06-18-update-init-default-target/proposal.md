---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/checkpoint.py
  - src/review_gauntlet/targets.py
  - tests/test_init_targets.py
  - tests/test_targets.py
  - openspec/specs/review-sessions/spec.md
---

# Update init default target selection

**Change Type**: implementation

## Problem / Context

`review-gauntlet init` currently defaults to a usable latest checkpoint when one exists, but that checkpoint target is represented as a branch diff from the checkpoint `review_base_commit` to `HEAD`. This excludes staged, unstaged, and untracked worktree changes from the default session even though those changes are part of the developer's current review target.

When no latest checkpoint exists, the current default falls back to WORKTREE, which only reviews staged, unstaged, and untracked changes. The requested default is broader: start from checkpoint when available, otherwise review all eligible files so the first session establishes full coverage.

## Proposed Solution

Change plain `review-gauntlet init` target selection so that:

- If a usable latest checkpoint exists, the session target starts from that checkpoint's `review_base_commit` and includes both committed changes through `HEAD` and current uncommitted worktree changes.
- If no latest checkpoint exists, the session target is equivalent to explicit `--all`.
- If a latest checkpoint exists but is invalid, initialization continues to fail instead of silently falling back to all-files review.
- Explicit target flags keep their existing scoped semantics: `--worktree` reviews only worktree changes, `--all` reviews the full inventory, `--from/--to` reviews only that committed range, and `--commit` reviews only that commit.

## Acceptance Criteria

- Plain `review-gauntlet init` with a usable latest checkpoint creates review cells for eligible files changed between checkpoint base and `HEAD` plus eligible staged, unstaged, and untracked worktree files.
- Plain `review-gauntlet init` with no latest checkpoint records an ALL target and creates review cells from the full current review inventory.
- Plain `review-gauntlet init` with an invalid latest checkpoint fails with the existing checkpoint validation error behavior.
- Explicit `--from/--to`, `--commit`, `--worktree`, and `--all` behavior remains unchanged.
- Session metadata records enough target information to explain whether worktree changes were included with the checkpoint-derived default.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` default target fallback uses ALL when `target_from_latest_checkpoint(root)` returns no target.
- `src/review_gauntlet/checkpoint.py` and/or `src/review_gauntlet/targets.py` represent checkpoint-derived defaults as including worktree changes without changing explicit branch target semantics.
- `changed_files_for_target()` or its equivalent returns the union of checkpoint-to-HEAD paths and current worktree paths for checkpoint-derived default sessions.
- Tests in `tests/test_init_targets.py` cover checkpoint plus uncommitted changes and no-checkpoint all-files fallback.
- Tests in `tests/test_targets.py` cover the target-level union behavior and explicit target non-regression.
- `make check` passes.

## Out of Scope

- Changing review execution phases, finding resolution, checkpoint creation, or finalize behavior.
- Introducing Git linked worktree creation or removal.
- Changing explicit target flag parsing or making `--from/--to` include worktree changes by default.
- Treating invalid latest checkpoints as absent checkpoints.
