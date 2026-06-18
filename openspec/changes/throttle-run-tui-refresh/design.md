# Design: Throttle Run TUI Refresh

## Background

The run TUI currently treats every visual refresh as a full state refresh. That is expensive because `RunController.snapshot()` can call into status construction that walks the review universe, reads files for digests, checks target freshness, queries the ledger, and builds coverage projection.

The observed active session showed:

- `status_snapshot()` around 2.2 seconds per call;
- TUI automatic refresh scheduled every 0.25 seconds;
- parent `review-gauntlet run` process around 90-100% CPU while child agents continued independently.

The problem is not the existence of rich TUI rendering. The problem is coupling a high-frequency visual tick to a heavyweight repository-status recomputation.

## Design Goals

- Bound automatic full snapshot work during TUI operation.
- Keep useful liveness display visible while agents run.
- Preserve immediate feedback for user-triggered refresh and terminal state changes.
- Keep the first fix small and localized to the TUI layer.
- Avoid changing durable session truth, controller phase semantics, or adapter execution behavior.

## Proposed Approach

Introduce two refresh concepts inside `RunApp`:

1. **automatic refresh tick**
   - runs on the existing interval;
   - updates activity animation and render state;
   - calls `controller.snapshot()` only when the full-refresh throttle has expired;
   - otherwise reuses `self.snapshot`.

2. **forced full refresh**
   - used by initial mount, manual `r`, run completion callback, and state-changing actions that need immediate feedback;
   - always calls `controller.snapshot()` unless the controller has already returned a completed result that should be rendered directly.

The throttle interval should be long enough to prevent CPU saturation on repositories where one snapshot takes multiple seconds. A default around 2 seconds is acceptable as a first implementation because run-agent steps are long-running and precise sub-second coverage updates are not required. The interval should be represented as a named constant or constructor-visible value to make unit tests deterministic.

## Alternatives Considered

### Cache status in `RunSnapshotReadinessProvider`

Caching status-provider output could reduce work for all callers, not only TUI. It is more invasive because status freshness affects ready-prompt selection, finalization blockers, coverage projection, and controller behavior. It also needs explicit invalidation around state changes.

This is a good future optimization, but it is not the safest first fix for a live CPU saturation issue.

### Increase the TUI interval only

Changing `set_interval(0.25, ...)` to a larger value helps but still couples every render tick to heavy status recomputation. If `status_snapshot()` takes 2.2 seconds and the interval is 2 seconds, the TUI can still run continuously under load. It also reduces liveness animation unnecessarily.

### Disable coverage projection during run

This would reduce cost but removes useful UI information and does not address other expensive full snapshot paths such as target digest and current target cell rebuilding.

## Verification Strategy

- Unit tests with a fake controller should count `snapshot()` calls deterministically across automatic ticks and forced refreshes.
- Tests should simulate monotonic time to avoid sleeps.
- Existing render-state tests should continue to prove dashboard output remains stable.
- Full project verification remains `make check`.

## Risk Management

The main risk is stale display information. This is acceptable only within the explicit throttle window and only for automatic refresh. Manual refresh, completion, and interrupts must bypass the throttle so users can force current state and terminal states render promptly.
