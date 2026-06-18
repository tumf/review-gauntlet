---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/cli.py
  - tests/test_run_tui.py
  - openspec/specs/run-controller/spec.md
---

# Throttle Run TUI Refresh

**Change Type**: implementation

## Problem/Context

`review-gauntlet run` can keep its parent TUI process at roughly one full CPU core while waiting for agent subprocesses. In the observed repository, the parent `review-gauntlet run` process stayed around 90-100% CPU for more than 30 minutes even while the actual agent child process was blocked or idle.

The current TUI mounts a background refresh interval at 0.25 seconds. Each refresh calls `RunController.snapshot()`, which can rebuild active session status, current target cells, file digests, target digest freshness, and coverage projection. In the observed active session, one `RunSnapshotReadinessProvider.status_snapshot()` call took about 2.2 seconds, far longer than the 0.25 second refresh cadence.

This creates a runaway refresh loop: the TUI asks for expensive filesystem and database-derived state faster than that state can be recomputed.

## Proposed Solution

Throttle expensive full snapshot refreshes in the run TUI while preserving visible liveness.

The TUI SHALL separate lightweight display updates from expensive session status recomputation:

- lightweight activity animation, elapsed time display, and lifecycle age display may continue at a short render cadence;
- full `controller.snapshot()` refreshes SHALL be rate-limited during automatic background refresh;
- explicit user refresh, run-controller completion, and step boundary updates SHALL force a full snapshot refresh;
- the existing `--no-tui` behavior SHALL remain unchanged.

A minimal implementation should start in `src/review_gauntlet/run_tui.py` by adding a full-refresh throttle to `RunApp` instead of changing session semantics. Broader digest reuse or status-cache refactoring is intentionally deferred unless required to satisfy the CPU bound.

## Acceptance Criteria

- While `review-gauntlet run` TUI waits for an agent subprocess, automatic background refresh SHALL NOT call `RunController.snapshot()` on every 0.25 second render tick.
- The TUI SHALL still update visible liveness such as the activity frame, elapsed time, last-output age, or timeout remaining between full snapshots.
- Manual refresh via `r` SHALL force a fresh `RunController.snapshot()` regardless of throttle timing.
- Controller completion and interruption paths SHALL render a fresh terminal snapshot or result state without waiting for the throttle interval.
- Existing controller semantics for ready tasks, finalization, interrupts, adapter errors, and `--no-tui` SHALL remain unchanged.
- Tests SHALL prove that automatic background refresh is throttled and that manual refresh bypasses the throttle.
- Repository verification SHALL include `make check`.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/run_tui.py` has distinct code paths for automatic background refresh and forced refresh.
- Automatic background refresh reuses the previous `RunSnapshot` inside the throttle window and avoids calling `controller.snapshot()` every tick.
- Manual refresh and run completion force a full snapshot refresh.
- `tests/test_run_tui.py` or a focused adjacent test module covers the throttling behavior with a fake controller or equivalent deterministic fixture.
- A targeted test command covering the TUI refresh behavior passes.
- `make check` passes.
- `cflx openspec validate throttle-run-tui-refresh --strict` passes.

## Out of Scope

- Rewriting the run controller state model.
- Changing review, resolve, mark, finalize, or checkpoint semantics.
- Changing durable session ledger schema.
- Removing coverage projection from the TUI.
- Optimizing all digest computation paths globally.
- Changing the default `--no-tui` behavior or making non-TUI output the default.
