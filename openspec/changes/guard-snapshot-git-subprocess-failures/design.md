# Design: snapshot-safe git subprocess failures

## Failure path

The observed crash occurs in the dashboard refresh path, not in external review adapter execution:

1. `RunApp.refresh_view()` asks the controller for a snapshot.
2. `RunController.snapshot()` calls `_status_snapshot()` and `_ready_prompt()`.
3. `_ready_prompt()` calls `_finalize_reasons()` to decide whether a finalize-ready prompt is available.
4. `_finalize_reasons()` runs git cleanliness checks via `assert_review_universe_clean()` and `classify_working_tree_dirty()`.
5. Those helpers call subprocess-backed git commands with captured stdout/stderr.
6. If the process is near its open-file limit, pipe creation raises `OSError(errno.EMFILE)` before git starts.

Because the exception is not a dirty-worktree result and not a disappeared-session `LookupError`, it escapes into the TUI event loop and crashes the process.

## Design principles

- Status/readiness checks are diagnostic. They should degrade conservatively when git cannot be inspected.
- Finalization is state-changing. It must remain strict and must not write checkpoint files if cleanliness cannot be verified.
- The UI must not claim readiness when an underlying safety check is unavailable.
- Resource exhaustion should be visible as a blocker, not hidden as success or swallowed silently.

## Proposed handling

Use a conservative blocker such as `git status checks unavailable due to resource exhaustion` when git subprocess startup fails during finalization-readiness checks.

For `RunController.snapshot()`, the preferred behavior is:

- Preserve any status data that was already computed.
- Set `next_ready_prompt` to `None` when readiness cannot be computed safely.
- Keep rendering the dashboard instead of propagating the exception.
- Surface the blocker through `finalize_blockers` where the status path can provide it.

For `finalize`, the same unavailable git cleanliness state blocks checkpoint writing.

## Testing strategy

Tests should monkeypatch the git subprocess boundary or helper boundary to raise `OSError(errno.EMFILE, "Too many open files")`. They should not try to exhaust real file descriptors.

Coverage should prove both surfaces:

- Non-mutating status/TUI surfaces stay alive and show conservative blockers.
- Mutating finalize surface refuses to write checkpoint artifacts.
