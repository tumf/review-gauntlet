# Design: Fix agent quiet during output

## Architecture Overview

```
TUI Thread (0.25s refresh)          Controller Thread (blocking run)
─────────────────────────           ────────────────────────────────
snapshot()                          _command_runner(config, root, state_dir, prompt)
  └─ _current_agent_lifecycle()       └─ Popen(stdout=PIPE, stderr=PIPE)
       └─ _agent_output_progress          ├─ stdout reader thread → push("stdout", line)
            .snapshot()                   └─ stderr reader thread → push("stderr", line)
            → (age, tail)                           │
                                          AgentOutputProgress ← shared, lock-protected
```

## Thread Safety Model

`AgentOutputProgress` uses a single `threading.Lock` to protect:
- `_last_output_at: datetime | None` — timestamp of most recent push
- `_output_lines: list[AgentOutputEntry]` — rolling buffer (last 20 entries)

Writers: stdout/stderr reader daemon threads call `push()`.
Reader: TUI thread calls `snapshot()` via `_current_agent_lifecycle()`.

Both operations are O(1) amortized (bounded list size), so lock contention is negligible.

## Subprocess I/O Design

Two daemon threads read from `process.stdout` and `process.stderr` pipes independently. This is the standard Python pattern (same approach as `Popen.communicate()` internally) to avoid deadlock when both pipes have data.

After `process.wait()`, both reader threads are joined with a timeout to ensure all buffered lines are captured before building the final `SessionCommandResult`.

## Backward Compatibility

The `CommandRunner` type alias remains `Callable[[CommandAdapterConfig, Path, Path, str], SessionCommandResult]`. The `output_progress` parameter is added only to the internal `_run_session_command_step()` as an optional keyword argument. Test mocks that use 4-parameter lambdas are unaffected.

The wiring in `_cmd_run()` uses a closure that captures `controller` and reads `controller.agent_output_progress` at call time (after `run()` has set it). This avoids changing any public API.
