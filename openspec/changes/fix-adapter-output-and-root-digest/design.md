# Design: Fix Adapter Output and Root Digest Edge Cases

## Scope

This change closes the remaining confirmed review findings without changing normal command adapter usage. It also fixes the discovered default-root status regression because it affects the same review freshness path that finalization depends on.

## Decisions

- Keep the existing one-run review model: failed cells remain retryable and successful cells in the same run can still persist coverage.
- Convert unexpected adapter exceptions into the same structured failure surface used by `ReviewAdapterError`, so callers do not need a separate traceback-handling path.
- Forbid `{prompt}` only in `adapter.output.path`. Prompt is still intentionally available to `args` and `env` because that is the adapter prompt transport contract.
- Create output parent directories only after containment validation to avoid turning unsafe path templates into filesystem side effects.
- Resolve the repository root once in digest functions and use that resolved root consistently for traversal and relative-path computation.

## Verification Strategy

Use command-adapter integration tests because subprocess output behavior and failure artifacts are part of the contract. Use target unit tests for digest root normalization because that behavior is deterministic and does not require adapter execution.
