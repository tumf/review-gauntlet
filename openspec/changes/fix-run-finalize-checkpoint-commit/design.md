# Design: Safe fallback checkpoint allowlisting for run finalization

## Current flow

`RunController.run()` detects successful finalization when an agent command returns successfully and the active session marker no longer exists. It then calls `_commit_finalized_checkpoint()`, which parses `generated_files` from the agent command stdout and passes those paths to `commit_latest_checkpoint()`.

This works only when the adapter stdout is pure JSON containing generated checkpoint paths. It fails for agent adapters that wrap command output in logs or prose, because JSON parsing returns no generated files.

## Chosen approach

Keep `RunController` as the orchestrator and fix the source of truth boundary in `commit_latest_checkpoint()`.

The commit helper already owns checkpoint-only staging safety. It should not depend solely on LLM or adapter stdout for the allowlist. When explicit generated paths are absent or incomplete, it can derive deterministic paths from the checkpoint files that `write_latest_checkpoint()` just published:

1. Read `.review-gauntlet/checkpoints/latest` as a pointer file.
2. Validate that the pointer content is a path-safe checkpoint id.
3. Resolve `.review-gauntlet/checkpoints/<checkpoint_id>/` inside the repository.
4. Add only the four standard checkpoint artifacts under that directory to the allowed commit paths.
5. Continue to block all other dirty paths.

This uses repository state as the source of truth, not the agent's self-report.

## Safety model

The fallback must be intentionally narrow:

- no symlink pointer
- no directory pointer
- no empty, nested, parent-traversal, absolute, or non-ASCII checkpoint id
- no broad `.review-gauntlet/checkpoints/` staging
- no ledger, run log, active-session, or worktree artifact staging
- no unrelated checkpoint generations except the current latest one

If the latest pointer cannot be validated, the helper should simply not add fallback paths. Existing blocker behavior will surface the dirty checkpoint files instead of silently committing unsafe paths.

## Tradeoffs

This keeps the automatic commit behavior useful for real agent adapters while preserving the conservative staging boundary. The alternative would be forcing every adapter to emit machine-only finalize JSON, but that is brittle for CLI agents whose stdout is optimized for humans or includes progress logs.

## Verification strategy

Unit tests cover the checkpoint helper's path allowlisting and blockers. Integration tests cover the run finalization path where stdout is non-JSON, because that is the user-visible failure mode.
