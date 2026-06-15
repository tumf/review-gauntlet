---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/run_controller.py
  - tests/test_cli.py
  - tests/test_run_controller.py
---

# Handle `review-gauntlet run` KeyboardInterrupt without traceback

**Change Type**: implementation

## Problem / Context

A developer can interrupt `review-gauntlet run` with Ctrl-C while the command is running in text mode or after TUI fallback. Today, `KeyboardInterrupt` can propagate to Python's top-level entrypoint and print a traceback. That is noisy and misleading for a normal user action.

`review-gauntlet run` already models incomplete active sessions as structured failures. User interruption should follow the same principle: keep the active session visible, avoid traceback output, and return a clear interrupted result.

## Proposed Solution

Update `review-gauntlet run` interrupt handling so Ctrl-C becomes a normal run outcome rather than an uncaught Python exception.

The implementation should:

- Catch `KeyboardInterrupt` around run execution paths that can block in controller execution, TUI execution, fallback text execution, or subprocess execution.
- Convert user interruption into a run result with `completed: false`, `reason: interrupted`, and an actionable `error` message.
- Preserve existing exit behavior by exiting non-zero when the active session remains incomplete.
- Preserve JSON mode by printing parseable JSON instead of traceback when interrupted.
- Preserve text mode by printing a short interrupted result instead of traceback.
- Ensure any running session-level subprocess is not left intentionally detached by the CLI interrupt path.
- Keep non-run commands' existing behavior unless they already have explicit interrupt semantics.

## Acceptance Criteria

- Pressing Ctrl-C during `review-gauntlet run` does not print a Python traceback.
- `review-gauntlet run --format json` interrupted by Ctrl-C emits parseable JSON with `completed: false`, `reason: interrupted`, `step_count`, `steps`, and `session_id` fields.
- Text output interrupted by Ctrl-C emits a concise interrupted result or message and exits non-zero.
- If a session remains active after interruption, the active-session marker remains available for later continuation.
- If a session-level subprocess is running when interruption happens, the CLI handles cancellation deterministically and records or reports the interrupted run outcome.
- Existing failure cases for command failure, no-ready-task, max-step exhaustion, and successful finalization remain unchanged.

## Explicit Completion Conditions

This change is complete when repository evidence shows all of the following:

- `src/review_gauntlet/cli.py` and/or `src/review_gauntlet/run_controller.py` catch `KeyboardInterrupt` for the `run` execution path and map it to a structured interrupted result.
- JSON-mode interrupt tests parse stdout as JSON and assert `reason == "interrupted"` with no traceback text.
- Text-mode interrupt tests assert no `Traceback` is printed and exit code is non-zero.
- Subprocess-interrupt behavior is covered by a fake or controlled command runner test so the test suite does not rely on a manually pressed Ctrl-C.
- Existing `run --format json` behavior tests still pass.
- `make check` passes.

## Out of Scope

- Changing `review-gauntlet review` Ctrl-C behavior unless needed to avoid shared helper regressions.
- Adding resumable partial subprocess output streaming.
- Changing TUI installation or fallback selection rules.
- Changing the meaning of successful session finalization.
