---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/run_tui.py
---

**Change Type**: implementation

# Fix agent "quiet" status shown during active stdout output

## Problem/Context

When `review-gauntlet run` executes an agent subprocess, the TUI displays "quiet" status after 5 seconds even though the agent is actively producing stdout output. This happens because `_run_session_command_step()` uses `subprocess.run(capture_output=True)`, which blocks until the process completes and provides no intermediate output to the controller.

During the blocking `subprocess.run()` call:
- `output_tail` remains empty (no output captured yet)
- `last_output_age_seconds` is computed from `_agent_step_started_at` (step start time), growing continuously
- After 5 seconds, `_current_agent_lifecycle()` flips status from "running" to "quiet"
- The Activity panel shows no output lines

This violates Constitution Principle 4: "Unknown must stay visible" — the system falsely reports the agent as quiet when it is actively producing output.

## Proposed Solution

Introduce a thread-safe `AgentOutputProgress` shared state object and switch subprocess execution from blocking `subprocess.run()` to `Popen` with line-by-line reading via reader threads.

1. **`AgentOutputProgress` class**: Thread-safe mailbox with `push(stream, text)` (called from command runner thread) and `snapshot()` returning `(last_output_age_seconds, output_tail)` (called from TUI thread)
2. **Popen with reader threads**: Replace `subprocess.run(capture_output=True)` with `subprocess.Popen()` + two daemon reader threads (one for stdout, one for stderr) that call `progress.push()` on each line
3. **Live lifecycle updates**: `_current_agent_lifecycle()` reads from `AgentOutputProgress` when available, computing `last_output_age` from the timestamp of the most recent output line instead of the step start time
4. **Backward-compatible wiring**: `output_progress` is an optional keyword argument; existing test mocks with 4-parameter `CommandRunner` signatures continue to work unchanged

## Acceptance Criteria

- While an agent subprocess is producing stdout, TUI displays "running" (not "quiet") and `last_output_age_seconds` reflects time since the most recent output line
- The Activity panel shows live output tail entries during agent execution, not only after process completion
- After 5 seconds of no output from a running agent, TUI correctly displays "quiet"
- All existing `CommandRunner` test mocks with 4-parameter signatures continue to work without modification
- No deadlocks from pipe reading (stdout/stderr read concurrently via threads)
- Timeout, interrupt, and error handling behavior remain unchanged

## Explicit Completion Conditions

- `AgentOutputProgress` class exists in `run_controller.py` with `push()` and `snapshot()` methods, protected by `threading.Lock`
- `RunController._agent_output_progress` field is created before command execution and cleared after
- `RunController._current_agent_lifecycle()` reads live output age from `_agent_output_progress.snapshot()` when the progress object is available
- `_run_session_command_step()` uses `subprocess.Popen` with reader threads instead of `subprocess.run(capture_output=True)`
- `_cmd_run()` wires `controller.agent_output_progress` into the command runner via closure
- Unit tests verify: thread-safe push/snapshot, live lifecycle shows "running" during output, "quiet" after 5s silence
- `python -m pytest tests/test_run_controller.py tests/test_cli.py tests/test_cli_run.py` all pass

## Out of Scope

- PTY emulation for subprocesses that buffer stdout when not connected to a TTY
- Changes to the Activity panel rendering logic in `run_tui.py` (it already renders `output_tail[-6:]`)
- Streaming output for the concurrent review adapter (`review_adapter.py`) — this proposal only covers session command execution
