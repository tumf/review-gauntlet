---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/checkpoint.py
  - tests/test_run_controller.py
  - tests/test_cli.py
---

# Commit checkpoint after run finalization

**Change Type**: implementation

## Problem / Context

`review-gauntlet finalize` writes deterministic latest checkpoint files and marks the active session finalized, but the normal non-merge path does not create a git commit for those checkpoint artifacts. `review-gauntlet run` currently treats finalization as complete once the active session marker disappears after an agent step, so a completed run can leave the newly generated checkpoint files uncommitted.

That makes the checkpoint less durable as the next review base and leaves the user with an extra manual step after an otherwise automated `run` flow.

Current relevant behavior:

- `RunController.run()` detects finalization by checking that `store.active_path` no longer exists after a successful command step.
- `_finalize(...)` writes `.review-gauntlet/checkpoints/latest/...` and removes the active session marker.
- The `--merge` Git-worktree finalize path already commits checkpoint artifacts inside the session worktree, but the normal finalize path does not.
- Existing `ready` prompt text asks the agent to commit intended source changes before finalizing; this proposal does not change that responsibility.

## Proposed Solution

After `review-gauntlet run` detects successful session finalization, it SHALL attempt a checkpoint-only git commit for the generated latest checkpoint artifacts.

The post-finalize commit behavior SHALL:

- Stage only `.review-gauntlet/checkpoints/latest` and the concrete generated checkpoint files reported by finalization artifacts when available.
- Never stage or commit product/source files, unrelated review artifacts, or non-checkpoint worktree changes.
- Use a deterministic commit message such as `checkpoint: finalize review-gauntlet session <session_id>`.
- Return structured checkpoint commit metadata in the `run` result.
- Treat a clean/no-op checkpoint diff as a successful no-op with an explicit reason.
- Treat non-checkpoint dirty worktree state as a blocker for the automatic checkpoint commit and make that blocker visible in the `run` result.

## Acceptance Criteria

- A successful `review-gauntlet run` that finalizes a session commits the latest checkpoint artifacts when those artifacts produce a git diff.
- The commit stages only checkpoint paths and does not include source/product files or unrelated worktree changes.
- The `run` result includes structured fields indicating whether a checkpoint commit was attempted, whether it was created, the resulting commit SHA when created, and a reason when no commit was created.
- If checkpoint files have no diff to commit, `run` completes successfully and reports a no-op checkpoint commit reason.
- If non-checkpoint dirty files are present after finalization, `run` does not auto-commit anything outside checkpoint paths and reports a visible blocker instead of silently succeeding.
- Existing `review-gauntlet finalize` behavior remains unchanged unless called through `run` finalization handling.
- Existing `finalize --merge` Git-worktree merge behavior remains unchanged and is not double-committed by the new normal-run checkpoint commit path.
- JSON output and text/TUI completion output remain parseable and include the new checkpoint commit status where applicable.

## Explicit Completion Conditions

This change is complete when:

- `RunController.run()` or its run-command integration path invokes a checkpoint-only commit step after detecting finalization.
- The checkpoint commit helper stages only allowed checkpoint paths and refuses to include unrelated worktree changes.
- The helper returns typed or structured result data covering committed, no-op, blocked, and failed states.
- Unit or integration tests prove that a finalized run creates a checkpoint commit when checkpoint files changed.
- Tests prove that unrelated dirty files are not staged or committed by the checkpoint commit helper.
- Tests prove that no checkpoint diff is reported as an explicit successful no-op.
- Existing finalize, ready, and merge-finalize tests continue to pass.
- `uv run pytest tests/test_run_controller.py tests/test_cli.py` passes.
- `make check` passes, or any failure is documented with unrelated evidence.

## Out of Scope

- Automatically committing product/source changes before finalization.
- Changing the `review-gauntlet finalize` standalone command to always commit.
- Changing `finalize --merge` session-worktree merge semantics.
- Adding push, branch creation, PR creation, or remote publishing behavior.
- Changing checkpoint file format or latest-only checkpoint layout.
- Rewriting the ready prompt beyond any minimal wording needed to avoid conflicting with the new run behavior.
