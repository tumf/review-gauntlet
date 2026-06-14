---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/review_adapter.py
  - src/review_gauntlet/config.py
  - openspec/specs/review-sessions/spec.md
  - README.md
---

# Add `review-gauntlet run` session orchestrator

**Change Type**: implementation

## Problem / Context

Review Gauntlet currently exposes the session state and the next continuation task through `ready`, but users must write an external shell loop to keep feeding those tasks to an agent until the session finishes. That makes the normal workflow harder to discover and shifts session progression control outside the tool even though Review Gauntlet already owns review planning, coverage state, finding lifecycle state, and active-session completion checks.

The project constitution says `review` advances exactly once. This change keeps that invariant: `review` remains the low-level single-batch operation, while `run` becomes a separate higher-level session orchestrator.

## Proposed Solution

Add a top-level session command:

```bash
review-gauntlet run [ROOT] [--max-steps N] [--config PATH] [--format text|json]
```

`run` repeatedly asks the existing `ready` logic for the next task prompt, invokes the configured command adapter as a session-level task runner with that prompt, waits for the external agent to finish, and then re-evaluates the active session. The command stops successfully when finalization removes the active-session marker, and stops unsuccessfully when there is no actionable ready task, the configured command fails, or the maximum step count is reached while the session is still active.

The `run` command must not add a second task-selection implementation. The existing `ready` prompt computation remains the single source of truth for continuation tasks.

## Acceptance Criteria

- `review-gauntlet run` exists in CLI parsing, help output, and shell completion metadata.
- `run` uses the same ready task decision path as `review-gauntlet ready`; it does not duplicate task priority logic.
- `run` reuses existing adapter configuration discovery and the configured command/args/cwd/env/timeout settings.
- `run` treats the adapter invocation as session-level task execution, not as review-cell OCR verdict collection.
- `run` expands `{prompt}` to the ready prompt and supports session-level variables needed by bundled presets.
- `run` exits `0` when the active session has been finalized and the active-session marker no longer exists.
- `run` exits `1` when no ready task exists while an active session remains.
- `run` exits `1` when the configured command cannot start, times out, or returns non-zero.
- `run --max-steps N` prevents unbounded looping and exits `1` if the session remains active after `N` steps.
- README quick-start and basic usage present `review-gauntlet run` as the recommended progression command.
- README keeps `ready` documented as an advanced/debug/custom-orchestrator API and removes the shell loop from recommended usage.

## Explicit Completion Conditions

This proposal is complete when repository evidence shows all of the following:

- `src/review_gauntlet/cli.py` registers and dispatches a `run` subcommand with `ROOT`, `--max-steps`, `--config`, and `--format` support.
- The implementation has a session-level configured-command execution path that is separate from review-cell verdict parsing and does not require OCR verdict JSON from the external agent.
- Tests cover success, no-ready-task failure, command failure, timeout/start failure where practical, and `--max-steps` behavior.
- Tests prove `run` consumes the same prompt returned by `ready` for at least one active-session scenario.
- Documentation examples recommend `review-gauntlet run` for normal session progression.
- `make check` passes.

## Out of Scope

- Changing `review` semantics or making `review` auto-loop.
- Removing or deprecating `ready`.
- Changing finding states, coverage computation, or finalization rules.
- Introducing multi-agent orchestration.
- Introducing a background daemon, notification system, or HITL UI.
- Auto commit, auto push, or auto merge by Review Gauntlet itself.
- Changing the adapter configuration schema unless strictly required for validation of session-level template variables.
