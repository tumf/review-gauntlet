## Implementation Tasks

- [ ] Add `AgentOutputProgress` class to `run_controller.py` with thread-safe `push(stream, text)` and `snapshot() -> (float | None, tuple[AgentOutputEntry, ...])` methods using `threading.Lock` (verification: unit - `tests/test_run_controller.py` test that push from one thread and snapshot from another returns correct age and tail entries)

- [ ] Add `_agent_output_progress: AgentOutputProgress | None` field to `RunController.__init__` and expose `agent_output_progress` property (verification: unit - `tests/test_run_controller.py` test that property returns None initially and returns the progress object during command execution)

- [ ] Update `RunController.run()` to create `AgentOutputProgress()` before calling `_command_runner()` and clear it to `None` after command completes (verification: unit - `tests/test_run_controller.py` test that `_agent_output_progress` is set during command execution and None before/after)

- [ ] Update `_current_agent_lifecycle()` to read `last_output_age` and `output_tail` from `_agent_output_progress.snapshot()` when the progress object has live output; fall back to existing `_agent_step_started_at` computation when no progress or no output yet (verification: unit - `tests/test_run_controller.py` test that snapshot returns status="running" with low last_output_age when progress has recent push, and status="quiet" when progress has no push for 5+ seconds)

- [ ] Add `output_progress: AgentOutputProgress | None = None` optional keyword argument to `_run_session_command_step()` in `cli.py` (verification: unit - existing `tests/test_cli_run.py` tests pass unchanged because the parameter defaults to None)

- [ ] Replace `subprocess.run(capture_output=True)` with `subprocess.Popen(stdout=PIPE, stderr=PIPE)` + two daemon reader threads for stdout/stderr in `_run_session_command_step()`. Each reader thread calls `output_progress.push()` per line when progress is not None. Preserve timeout, interrupt, and error handling semantics (verification: integration - `tests/test_cli_run.py::test_run_session_command_expands_repo_root_state_dir_and_defaults_cwd` continues to pass; new test that a slow subprocess's output lines arrive via push before process exit)

- [ ] Update `_cmd_run()` to wire `controller.agent_output_progress` into the command runner closure so the real command runner receives the live progress object (verification: integration - `tests/test_cli_run.py` run command tests pass; manual - run `review-gauntlet run` with TUI and observe that the agent panel shows "running" and activity lines during agent execution)

## Future Work

- Verify with real long-running agent commands that pipe buffering does not delay output excessively (requires manual testing with actual review adapters)
- Consider extending streaming output to the concurrent review adapter in `review_adapter.py`

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate fix-agent-quiet-during-output --archive-gate`
