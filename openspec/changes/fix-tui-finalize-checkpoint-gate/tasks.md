## Implementation Tasks

- [ ] Update `RunController.run()` finalize-success branches to record terminal finalized state before returning. Completion condition: the branch beginning `if not self.store.active_path.exists():` sets `self._agent_status` to `"finalized"` and updates `self._agent_lifecycle` to a terminal non-running lifecycle before `_run_result(...)` is returned. (verification: unit - `tests/test_run_controller.py`)

- [ ] Cover the final snapshot state after agent-driven finalize. Completion condition: `tests/test_run_controller.py` asserts `controller.snapshot().agent_status == "finalized"` after a command removes the active session and the run completes. (verification: unit - the test fails before the controller state fix because the snapshot remains non-finalized)

- [ ] Cover the TUI finalized snapshot rendering contract. Completion condition: `tests/test_run_tui.py` asserts a finalized snapshot with no active session state renders `Finalize checkpoint` as `done complete` and a finalized header/gate state. (verification: unit - `tests/test_run_tui.py`)

- [ ] Preserve failure and blocked branch semantics. Completion condition: existing run-controller tests for command failure, interruption, and max-steps exhaustion with an active session continue to pass without converting those states to finalized. (verification: unit - `tests/test_run_controller.py`)

## Future Work

- Manual verification may be performed by running an actual `review-gauntlet run` TUI session through finalization and observing that gate 6/6 changes to `done complete`.

## Final Validation

Expected archive gate: `cflx openspec validate fix-tui-finalize-checkpoint-gate --archive-gate`
