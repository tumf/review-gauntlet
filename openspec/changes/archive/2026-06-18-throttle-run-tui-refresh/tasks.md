## Implementation Tasks

- [x] Add a throttled automatic refresh path to `src/review_gauntlet/run_tui.py` so `RunApp._background_refresh()` does not call `controller.snapshot()` on every 0.25 second tick while a prior full snapshot remains fresh. (verification: unit - add a focused test in `tests/test_run_tui.py` with a fake controller; repeated automatic refreshes inside the throttle window increment liveness/render state while the fake controller's `snapshot_call_count` remains unchanged after the first full refresh)
- [x] Preserve forced refresh behavior for user and terminal events: `action_refresh()`, `_run_controller()` completion callbacks, interrupt/stop actions where they render immediate feedback, and initial mount SHALL still use a fresh `controller.snapshot()`. (verification: unit - add `tests/test_run_tui.py` cases proving manual refresh and completion refresh each increment the fake controller's `snapshot_call_count` even when automatic refresh TTL has not expired)
- [x] Keep liveness display moving between full snapshots by updating activity frame and/or derived render timing from the cached snapshot without redoing expensive status computation. (verification: unit - add a `tests/test_run_tui.py` render-state test proving an automatic tick within the throttle window changes the activity/liveness display state while `snapshot_call_count` does not increase)
- [x] Avoid changing session semantics outside the TUI: `RunController.run()`, ready-prompt selection, finalize behavior, adapter execution, and `--no-tui` fallback SHALL keep their existing behavior. (verification: integration - existing `tests/test_run_controller.py` and CLI run tests continue to pass under `make check`)
- [x] Add regression coverage documenting the CPU-protection contract: automatic TUI refresh frequency SHALL be bounded independently from expensive snapshot cost. (verification: unit - `tests/test_run_tui.py` or an adjacent focused test asserts multiple timer ticks produce at most one full snapshot within the configured throttle interval)
- [x] Run targeted and full project verification after implementation. (verification: integration - run a focused pytest command for the new TUI refresh tests, then `make check`)

## Future Work

- Add a broader status-context cache or digest reuse layer for `RunSnapshotReadinessProvider`, `_current_target_cells()`, `target_digest()`, and coverage projection if profiling after this change still shows unacceptable CPU or latency.
- Add optional benchmark instrumentation for large repositories to track `status_snapshot()` wall time over time.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal validation: `cflx openspec validate throttle-run-tui-refresh --strict`
Expected evidence validation: `cflx openspec validate throttle-run-tui-refresh --strict --evidence warn`
Expected archive gate: `cflx openspec validate throttle-run-tui-refresh --archive-gate`
