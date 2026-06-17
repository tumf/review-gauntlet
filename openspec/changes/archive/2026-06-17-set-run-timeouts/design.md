# Design: Set run command timeout defaults and add quiet timeout

## Request classification

Requested Artifact: implementation

The requested change affects runtime behavior, configuration schema, persisted failure diagnostics, TUI display, tests, and documentation. It is therefore an implementation proposal, not spec-only.

## Current behavior

`CommandAdapterConfig.timeout_seconds` defaults to 600 seconds. `_run_session_command_step()` starts the external command, reads stdout/stderr on background threads, then calls `process.wait(timeout=config.timeout_seconds)`. `RunController._current_agent_lifecycle()` derives `quiet` from output liveness, using `AGENT_QUIET_THRESHOLD_SECONDS = 5.0`, but quiet is only a display state.

## Target behavior

Two time budgets should coexist:

1. Overall command timeout: the maximum wall-clock duration for the adapter command. Default: 3600 seconds.
2. Quiet timeout: the maximum allowed duration with no stdout/stderr output while the adapter command is still running. Default: 600 seconds.

Quiet timeout should be enforced before the overall timeout when applicable. The shorter remaining deadline between the overall timeout and quiet timeout should drive the next wait/poll interval.

## Failure reason model

Quiet timeout should use a distinct structured failure reason, `quiet_timeout`, rather than overloading `timeout`. This preserves the existing requirement that external-agent and orchestration failure reasons remain distinct.

Human-facing TUI wording may stay in the timeout family, but detailed diagnostics should expose that the timeout was caused by output silence rather than total wall-clock duration.

Expected quiet-timeout failure payload fields include:

- `reason`: `quiet_timeout`
- `error`: concise human-readable message
- `quiet_timeout_seconds`: configured quiet timeout
- `timeout_seconds`: configured overall timeout
- `returncode_after_kill`: subprocess return code after termination

The existing overall timeout path should continue to use `reason: timeout`.

## Output-liveness source

The subprocess reader threads already see stdout/stderr line events. The implementation should avoid duplicating parsing by recording a shared last-output timestamp from the same read path that currently appends lines and pushes `AgentOutputProgress`.

When no output has been produced, quiet elapsed time starts at process start. When output is produced, quiet elapsed time restarts from that output timestamp. Both stdout and stderr count as liveness.

## Polling approach

The current single `process.wait(timeout=config.timeout_seconds)` call cannot enforce a second inactivity deadline. Replace it with a bounded loop such as:

- Start process and stream reader threads.
- Record `started_at` and `last_output_at`.
- Repeatedly check whether the process has exited.
- Compute remaining overall timeout from `started_at`.
- Compute remaining quiet timeout from `last_output_at` or `started_at`.
- Wait/poll only until the nearest deadline or a small bounded interval.
- On deadline, kill the process and persist the appropriate failure payload.

This must remain responsive to `KeyboardInterrupt` and should preserve stdout/stderr artifact persistence on all exit paths.

## TUI integration

Before quiet timeout, `quiet` remains a non-terminal lifecycle state. After quiet timeout, the terminal state should render as timed-out family wording. The structured reason `quiet_timeout` should be mapped alongside `timeout` for lifecycle status and TUI status classification, while preserving enough detail to distinguish the cause in result/artifact data.

## Documentation

Documentation should describe:

- `timeout_seconds`: total adapter wall-clock timeout, default 3600 seconds / 60 minutes.
- `quiet_timeout_seconds`: no-output adapter timeout, default 600 seconds / 10 minutes.
- stdout and stderr output both reset the quiet timeout.
- quiet display before the threshold is not itself a failure.
