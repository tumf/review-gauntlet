---
change_type: implementation
priority: high
dependencies:
  - preserve-interrupted-review-results
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/review_adapter.py
  - tests/test_review_progress.py
  - tests/test_cli_session_review.py
  - openspec/specs/review-sessions/spec.md
---

# Handle review interrupt cleanly

**Change Type**: implementation

## Problem/Context

When `review-gauntlet review` is interrupted with `Ctrl-C`, the raw `KeyboardInterrupt` currently escapes to the CLI entrypoint. Users see a Python traceback instead of an actionable command result. This is noisy for humans, difficult for agents to parse, and obscures the durable session state that remains available after interruption.

This proposal depends on completed-cell preservation so the clean interrupt response can accurately report persisted work and pending work.

## Proposed Solution

Treat review interruption as a first-class command outcome. Catch review-time `KeyboardInterrupt` or a domain-specific interruption signal at the review command boundary, cancel adapter work, preserve completed results as defined by the dependency proposal, then emit a concise interrupted result without a traceback.

For `--format json`, stdout should remain parseable JSON with `interrupted: true`, the run id, persisted reviewed count, cancelled or pending cell details when available, and normal status fields. For human progress, stderr may include a short interruption summary, but it must not include a Python traceback.

## Acceptance Criteria

- Interrupting `review-gauntlet review` exits without printing a Python traceback.
- The command exits with status code `130` for user interruption.
- `--format json` emits parseable JSON that includes `interrupted: true`.
- Human stderr output includes at most concise progress/interruption messages and no uncaught stack trace.
- The adapter cancellation path still runs when interruption occurs.
- The active session remains active and retryable after interruption.

## Explicit Completion Conditions

- `main()` or `_cmd_review()` catches review interruption and prevents raw `KeyboardInterrupt` tracebacks from reaching the console.
- The interrupt response includes structured status output in JSON mode.
- Tests assert no `Traceback` appears for interrupted review command output.
- Tests assert exit code `130` for interrupted review execution.
- Existing adapter cancellation tests still pass.
- `make check` passes.

## Out of Scope

- Changing non-review command interruption behavior unless required to prevent review-time traceback leakage.
- Adding a new persistent session state such as `interrupted`.
- Automatically cancelling the active review session.
