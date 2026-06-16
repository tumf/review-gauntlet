---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/run_tui.py
  - tests/test_run_controller.py
  - tests/test_run_tui.py
---

# Fix TUI Finalize Checkpoint gate remains "later waiting" after finalize

**Change Type**: implementation

## Problem / Context

When `review-gauntlet run` completes via agent-driven finalize, the TUI's "Finalize Checkpoint" gate (gate 6/6) stays stuck at `later waiting` instead of transitioning to `done complete`.

Root cause:

- `RunController.run()` emits the `finalized` event and returns successfully, but never updates `self._agent_status = "finalized"`.
- After finalize, the active session file is deleted, so `snapshot()` catches `LookupError` and falls back to an empty status dict without `session_state`.
- `derive_finalize_gates()` in `run_tui.py` only considers `snapshot.agent_status == "finalized" or snapshot.session_state == "finalized"` to mark the checkpoint gate done.

Result: the final refresh after completion shows the gate as `later waiting`, even though the session has finalized.

## Proposed Solution

1. `RunController.run()` sets `self._agent_status = "finalized"` (and a terminal lifecycle) immediately before returning in both the "active session disappeared" finalize path and the "max_steps exhausted but session gone" path.
2. Add regression tests in `test_run_controller.py` and `test_run_tui.py` that assert `agent_status == "finalized"` and all gates render as `done complete` after finalize completion.
3. Keep the existing TUI logic unchanged; the fix is strictly in the controller's completion state.

## Acceptance Criteria

- After `RunController.run()` detects finalize via active session disappearance, `controller.snapshot().agent_status == "finalized"`.
- TUI dashboard renders `Finalize Checkpoint` as `done complete` (and header shows `FINALIZED`) for such snapshots.
- No behavior change for non-finalize completions (errors, interrupts, max-steps exhaustion with active session remain).
- All new tests pass `make check` (format, lint, typecheck, test).

## Explicit Completion Conditions

- `tests/test_run_controller.py` contains a test that inspects `controller.snapshot().agent_status` after the finalize branch and asserts `"finalized"`.
- `tests/test_run_tui.py` contains a test constructing a `RunSnapshot(agent_status="finalized", session_state=None, ...)` and asserts `derive_finalize_gates(...)` marks gate 6 as `done complete`.
- `make check` passes with no new failures or type errors.
- Running the TUI manually on a finalize scenario shows gate 6 as `done complete` immediately after the controller returns.

## Out of Scope

- Changing TUI gate derivation logic or adding new visual states.
- Altering finalize/commit behavior or checkpoint contents.
- Adding new CLI flags or configuration.
