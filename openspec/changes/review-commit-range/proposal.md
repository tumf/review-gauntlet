---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/targets.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/review_adapter.py
  - src/review_gauntlet/session_store.py
  - src/review_gauntlet/checkpoint.py
  - src/review_gauntlet/continuation.py
  - openspec/CONSTITUTION.md
---

**Change Type**: implementation

# Review Commit Range

## Problem / Context

review-gauntlet currently reviews the **working tree** (uncommitted changes). When the run agent fixes confirmed findings, the file digest changes → review cells become stale → stale cells trigger a new review → new findings are generated → infinite loop.

Root cause: review target and fix target share the same source (working tree). There is no git commit boundary separating "what should be reviewed" from "what the fix changed."

## Proposed Solution

Change the review target from **working tree** to **committed content**. Pin the review digest to a specific commit (session's `review_head_commit` = HEAD at init time). Fixes happen on the working tree but do not affect the review target.

### Core design

| Concern | Before | After |
|---------|--------|-------|
| Review digest source | `path.read_bytes()` (working tree) | `git show <commit>:<path>` (committed) |
| Default init target | `WORKTREE` (uncommitted) | Checkpoint → HEAD branch diff; fallback: commit HEAD |
| Fix changes | Change digest → stale cells → review loop | Working tree only; commit digest unchanged |
| `fixed_pending_paths` stale exception | Workaround for stale-on-fix | **Removed** (no longer needed) |
| verify-fixes digest | Working tree (same as review) | Working tree (different from review; deliberate) |
| `--worktree` flag | Supported | **Removed** |

### Flow

1. User commits work → `review-gauntlet init` (target: checkpoint → HEAD)
2. Session stores `review_head_commit`
3. `review` runs on committed content (`git show <sha>:<path>` digests)
4. `run` loop: triage → fix (working tree) → verify (working tree digest, different from review)
5. Agent commits fixes → `finalize` writes checkpoint at new HEAD
6. Next init reviews from checkpoint → new HEAD

## Acceptance Criteria

- `init` without flags defaults to checkpoint→HEAD branch target; falls back to commit HEAD
- `--worktree` flag is removed; `TargetKind.WORKTREE` is removed from `TargetSpec`
- Review cells use committed content digests (stable across fix phase)
- `_effective_current_target_coverage_for_cells` no longer uses `fixed_pending_paths` exception
- `verify-fixes` uses working tree digest (different source than review)
- Fix changes do not cause review cells to become stale
- Review prompts include commit sha ("at commit `<sha>`")

## Explicit Completion Conditions

1. `file_digests_at_commit(root, sha)` exists in `targets.py` and returns correct SHA256 of `git show <sha>:<path>`
2. `_cmd_init` stores `review_head_commit` in session metadata
3. `_current_target_cells()` reads digest from commit, not working tree, when `review_head_commit` is present
4. `_effective_current_target_coverage_for_cells` stale check is `persisted.digest != current.digest` only (no `fixed_pending_paths`)
5. Same simplification applied to `_reconcile_cells` and `_ready_review_cells`
6. `store.fixed_pending_paths()` removed (or kept but unused by stale logic)
7. `resolve_target()` no longer returns `WORKTREE` as default; `TargetKind.WORKTREE` removed
8. `--worktree` parser argument removed from `init`
9. Review prompt (`build_review_prompt`, `_build_file_scoped_ready_prompt`) includes commit sha
10. All 773 existing tests pass (updated where necessary)
11. New tests cover: `file_digests_at_commit`, commit-based stale suppression, verify-fixes working-tree path

## Out of Scope

- Automatic git commit during run loop
- `verify-fixes` prompting redesign (uses working tree existing behavior)
- Checkpoint format changes
- `report` command changes
