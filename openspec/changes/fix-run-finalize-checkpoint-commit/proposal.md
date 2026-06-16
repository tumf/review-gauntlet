---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/checkpoint.py
  - tests/test_checkpoint_commit.py
  - tests/test_run_controller.py
  - openspec/specs/review-sessions/spec.md
  - openspec/CONSTITUTION.md
---

# Fix run finalize checkpoint commit fallback

**Change Type**: implementation

## Problem/Context

`review-gauntlet run` is expected to commit checkpoint artifacts after an agent successfully finalizes the active session. The current implementation only allows concrete checkpoint artifact paths parsed from the agent step stdout. If the adapter output is not pure JSON, `checkpoint_generated_files_from_stdout()` returns an empty list, so `commit_latest_checkpoint()` only allows `.review-gauntlet/checkpoints/latest` and blocks the real generated checkpoint directory as non-checkpoint dirty state.

This regresses the intended run-finalize checkpoint commit behavior: the session is finalized, checkpoint artifacts are written, but the checkpoint commit is not created. The failure is visible as `blocked_by_non_checkpoint_changes` with generated checkpoint files in `checkpoint_commit_blocked_paths`.

The fix must preserve the project constitution principles: coverage and completion state remain explicit, deterministic, and not inferred from LLM self-reporting.

## Proposed Solution

Teach the checkpoint commit helper to safely recover the generated checkpoint artifact allowlist from the current `.review-gauntlet/checkpoints/latest` pointer when the explicit `generated_files` list is empty or incomplete.

The fallback should:

- resolve only the current latest pointer file, not symlinks or directories
- accept only a path-safe single-segment checkpoint id
- allow only the latest checkpoint directory's `status.json`, `findings.json`, `events.json`, and `summary.md`, plus the `latest` pointer file
- keep blocking unrelated source files and stale unrelated checkpoint artifacts
- keep standalone `finalize` and `finalize --merge` commit semantics unchanged

## Acceptance Criteria

- `review-gauntlet run` creates a checkpoint commit after an agent finalizes the session even when the agent stdout is not parseable JSON.
- `review-gauntlet run` creates a checkpoint commit when stdout omits `generated_files` or provides an incomplete checkpoint artifact list, as long as the latest pointer safely resolves to the generated checkpoint directory.
- The checkpoint commit stages only `.review-gauntlet/checkpoints/latest` and the four standard files under the latest generated checkpoint directory.
- Non-checkpoint dirty files still block the automatic checkpoint commit and remain unstaged.
- Dirty checkpoint artifacts outside the latest generated checkpoint directory still block the automatic checkpoint commit.
- Invalid latest checkpoint pointer shapes are not trusted for commit allowlisting.
- Standalone `review-gauntlet finalize` still writes checkpoint artifacts without creating the run-only checkpoint commit.
- `review-gauntlet finalize --merge` remains governed by the existing session-worktree commit and merge path, with no duplicate run-only checkpoint commit.

## Explicit Completion Conditions

The change is complete when:

- `src/review_gauntlet/checkpoint.py` derives safe allowed checkpoint commit paths from the latest pointer when explicit generated files are absent or incomplete.
- Regression tests in `tests/test_checkpoint_commit.py` prove real `write_latest_checkpoint()` output commits successfully with empty and incomplete `generated_files`.
- Regression tests prove invalid latest pointers and stale checkpoint artifacts remain blocked.
- A run-controller or CLI-level integration test proves an agent finalization with non-JSON stdout still results in checkpoint commit metadata reporting `checkpoint_committed: true`.
- `make check` passes.
- `cflx openspec validate fix-run-finalize-checkpoint-commit --strict` passes.

## Out of Scope

- Changing standalone `review-gauntlet finalize` to auto-commit.
- Changing `review-gauntlet finalize --merge` merge behavior.
- Trusting arbitrary files printed by an external agent.
- Adding user configuration to disable automatic checkpoint commits.
- Redesigning checkpoint storage layout or replacing the latest pointer format.
