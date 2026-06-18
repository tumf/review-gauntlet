---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/changes/archive/2026-06-18-review-commit-range/
  - src/review_gauntlet/targets.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/review_adapter.py
  - openspec/specs/review-sessions/spec.md
---

**Change Type**: implementation

# Revert: Commit-Range Review Target

## Problem / Context

The `review-commit-range` change (archived at `2026-06-18-review-commit-range`) pinned the review target to a git commit instead of the working tree. This removed `TargetKind.WORKTREE`, deleted `--worktree` flag, and switched digest computation to `git show <commit>:<path>`. While this successfully stopped the fix→stale→review loop, the same goal is already achieved by the subsequent "remove stale concept" refactor (`513c715`), which made stale cells non-blocking for finalization and re-review.

The commit-based approach introduces unnecessary complexity: `file_digests_at_commit()`, `_review_head_commit()`, `review_commit` in prompts, and `_git_bytes()` plumbing. Reverting to worktree-based reviews simplifies the codebase while the stale-free behavior (no re-review on fix) remains intact.

## Proposed Solution

Revert the `review-commit-range` implementation while preserving:

- `513c715` (remove stale concept from review logic, TUI, specs) — stale cells remain non-blocking
- `6631386` (stdout verdict size limit / thread join fix)
- `fix-tui-task-label-heuristic` merge

**Reverted items**:

| Area | Before revert (current) | After revert (target) |
|------|------------------------|-----------------------|
| `TargetKind` enum | BRANCH, COMMIT | BRANCH, WORKTREE, COMMIT, ALL |
| Init default | `TargetSpec(COMMIT, commit=HEAD, base_ref="__all__")` | `TargetSpec(WORKTREE)` |
| Init digests | `file_digests_at_commit(root, review_head_commit)` | `file_digests(root)` |
| `--worktree` flag | Rejected (exit 64) | Accepted (review uncommitted changes) |
| Session metadata | Includes `review_head_commit` | No `review_head_commit` |
| `_file_digests_for_session` | Routes to `file_digests_at_commit` if commit present | Always `file_digests(root)` |
| Review prompts | Include `review_commit: <sha>` | No commit reference |
| `review_adapter.PromptContext` | Has `review_commit` field | No `review_commit` field |
| `ExternalCommandReviewAdapter` | Reads files via `git show <commit>:<path>` | Reads from working tree |

**Preserved items**:

- Stale cells do not block finalization or trigger re-review (from `513c715`)
- `fixed_pending_paths()` remains removed from `session_store.py` (no longer needed)
- All TUI stale-removal changes stay

## Acceptance Criteria

- `TargetKind.WORKTREE` and `TargetKind.ALL` are valid enum members
- `review-gauntlet init --worktree` creates a session from uncommitted changes
- `review-gauntlet init` without flags defaults to WORKTREE (not COMMIT HEAD)
- Session metadata does not contain `review_head_commit`
- Review cells use `file_digests(root)` (working tree digests)
- Review prompts do not include commit SHA
- `file_digests_at_commit()` is removed from `targets.py`
- `_review_head_commit()` and `_metadata_review_commit()` are removed from `cli.py`
- `review_commit` parameter is removed from `review_adapter.py`
- All tests pass (`make check`)
- Stale cells remain non-blocking (no regression on `513c715`)

## Out of Scope

- Reverting `513c715` (remove stale concept) — intentionally kept
- Reverting `6631386` (stdout verdict / thread join)
- Reverting `fix-tui-task-label-heuristic`
- Removing the archived proposal directory (manual cleanup)

## Explicit Completion Conditions

1. `TargetKind.WORKTREE = "worktree"` and `TargetKind.ALL = "all"` exist in `targets.py`
2. `resolve_target()` accepts `worktree` parameter and returns WORKTREE as default
3. `_workspace_changed_files()` exists and handles staged/unstaged/untracked
4. `changed_files_for_target()` handles WORKTREE and ALL cases
5. `file_digests_at_commit()`, `_review_universe_files_at_commit()`, `_git_bytes()` removed from `targets.py`
6. `_review_head_commit()` and `_metadata_review_commit()` removed from `cli.py`
7. `_file_digests_for_session()` always returns `file_digests(root)`
8. `_cmd_init()` does not store `review_head_commit` in metadata
9. `_cmd_init()` uses `file_digests(root)` for init digests
10. `--worktree` argument restored in init parser
11. `review_commit` removed from `review_adapter.py` (PromptContext, _review_commit_prompt_lines)
12. `ExternalCommandReviewAdapter` reads from working tree (revert `git show` path)
13. All existing tests pass; updated expectations where removed behavior was tested
