---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/checkpoint.py
  - src/review_gauntlet/targets.py
  - src/review_gauntlet/subprocess_failures.py
  - tests/test_run_controller.py
  - tests/test_run_tui.py
  - tests/test_cli_session_review.py
---

# Guard snapshot git subprocess failures

**Change Type**: implementation

## Premise / Context

- After the subprocess resource-exhaustion change was proposed and merged, `review-gauntlet run` still crashes in TUI mode with `OSError: [Errno 24] Too many open files`.
- The new traceback shows a different path: `RunApp.refresh_view()` calls `RunController.snapshot()`, which calls `_ready_prompt()`, which calls `_finalize_reasons()`, which calls `assert_review_universe_clean()`, which calls `checkpoint._git("diff", "--name-only", "--cached")`.
- This happens during dashboard refresh/readiness calculation, before or outside the review adapter command path.
- `RunController.snapshot()` currently catches `LookupError` for disappeared sessions but does not protect the TUI from transient repository-status subprocess startup failures.
- The constitution requires failed and unknown states to stay visible. A TUI dashboard refresh should not turn a recoverable status/readiness problem into a process-killing traceback.

## Problem/Context

The prior fix handles subprocess startup failures for review adapter commands and run-agent commands. It does not cover subprocesses used by status/readiness/finalize-blocker calculation.

During TUI refresh, `snapshot()` asks for both session status and the next ready prompt. The ready-prompt path recomputes finalization blockers, including git dirty-state checks. If the process has many open file descriptors, `subprocess.run(... capture_output=True)` can fail while opening stdout/stderr pipes for `git diff --name-only --cached`. That `OSError` currently escapes through Textual refresh and crashes `review-gauntlet run`.

## Proposed Solution

Make run snapshot/readiness generation tolerant of repository-status subprocess startup failures.

- Convert `OSError` from git-based dirty-state/finalize checks into explicit finalize blockers or unavailable readiness state.
- Ensure TUI refresh can continue rendering a snapshot with existing coverage/findings/status data when readiness or finalize blocker computation cannot run because of resource exhaustion.
- Reuse the existing subprocess failure classification where possible so `EMFILE`/`ENFILE` are reported consistently.
- Preserve strict behavior for actual `finalize`: finalization must still fail safely and must not write checkpoint files when git cleanliness cannot be verified.

## Acceptance Criteria

- `review-gauntlet run` TUI refresh does not crash when `checkpoint._git()` or related git dirty-state subprocess calls raise `OSError(errno.EMFILE, ...)` during snapshot/readiness/finalize-blocker calculation.
- The snapshot or status output includes an explicit blocker or diagnostic indicating git status/checkpoint cleanliness could not be verified due to resource exhaustion.
- The ready prompt is omitted or conservatively blocked when finalization cleanliness cannot be checked; it must not claim finalize is ready.
- `review-gauntlet status --format json` and `review-gauntlet finalize --format json` fail or block with structured diagnostics rather than raw traceback when git cleanliness checks hit subprocess startup `OSError`.
- `finalize` remains safe: no checkpoint files are written if review-universe cleanliness or target digest freshness cannot be verified.
- Existing dirty-worktree blocker behavior remains unchanged when git commands succeed.

## Explicit Completion Conditions

- `_finalize_reasons()` or its git-cleanliness helpers handle `OSError` from git subprocess startup and add a conservative blocker instead of letting it escape in status/readiness paths.
- `RunController.snapshot()` and/or `_ready_prompt()` prevents readiness-generation failures from crashing TUI refresh while keeping the issue visible in snapshot data.
- `review-gauntlet finalize` and `status` tests cover git subprocess `EMFILE` failure and verify structured output/no checkpoint writes.
- TUI/run-controller tests cover snapshot refresh when readiness calculation hits `EMFILE`, proving no raw traceback and no false finalize-ready prompt.
- `make check` passes after implementation.

## Out of Scope

- Changing review adapter startup failure handling, already covered by the archived `handle-subprocess-resource-exhaustion` change.
- Automatically lowering concurrency further or changing runtime scheduling.
- Raising the OS open-file limit from inside review-gauntlet.
- Hiding dirty-worktree or target-digest blockers when git commands succeed.
