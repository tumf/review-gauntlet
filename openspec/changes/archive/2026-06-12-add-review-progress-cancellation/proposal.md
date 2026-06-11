---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/review_adapter.py
  - tests/test_cli.py
  - tests/test_init_targets.py
  - openspec/specs/review-sessions/spec.md
---

# Add Review Progress and Cancellation

**Change Type**: implementation

## Problem / Context

`review-gauntlet review` can appear to hang when it launches external command adapters for many selected review cells. The command currently waits for all selected cells to finish before emitting any output. With the default budget of 50, concurrency of 8, and command-adapter timeout of 600 seconds, an adapter such as `opencode run` may run for a long time while the user sees no progress.

Interrupt handling is also poor. `KeyboardInterrupt` occurs while waiting on `Future.result()`, but the `ThreadPoolExecutor` context manager then shuts down with `wait=True`, so the process can continue waiting for worker threads that are blocked in `subprocess.run()` on external adapter processes.

## Proposed Solution

Make `review-gauntlet review` observable while preserving the constitution requirement that one review command advances exactly one run. Because the CLI already defaults to `--audience human`, the default review experience should emit human-readable run and cell progress to stderr. When `--audience agent` is explicitly selected, progress display is unnecessary and must be suppressed so automation receives only the final structured stdout contract.

Make external command adapter execution cancellable. Replace the uncancellable `subprocess.run()` path with process-handle-based execution so interrupt handling can terminate in-flight adapter subprocesses and return control promptly. Cancellation must not mark unfinished cells as reviewed, and already committed successful cells must remain explicitly recorded.

## Acceptance Criteria

- `review-gauntlet review` emits an initial progress summary before launching adapter work for human audience output, including session id, run id, selected cell count, budget, concurrency, adapter identity when available, timeout, and artifact directory.
- `review-gauntlet review` emits per-cell start, completion, failure, timeout, and cancellation progress to stderr for human audience output.
- `--format json` stdout remains valid final JSON and is not polluted by progress messages.
- `--audience agent` suppresses decorative progress so automation receives only the existing final structured output contract on stdout.
- `KeyboardInterrupt` cancels pending futures, avoids waiting indefinitely for the executor, and terminates in-flight command adapter subprocesses.
- Interrupted or cancelled cells are not marked `reviewed`; previously committed successful cells and findings remain durable ledger entries.
- Command adapter stdout, stderr, failure, and command artifacts remain written per cell when available, including timeout and cancellation metadata.
- Existing success, failure, budget, concurrency, and one-run semantics are preserved.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` has an explicit progress-reporting path for `review` that writes progress only to stderr and respects `--audience`.
- `_review_cells_concurrently` or its replacement handles `KeyboardInterrupt` without relying on `ThreadPoolExecutor.__exit__` to wait for all workers before returning control.
- `src/review_gauntlet/review_adapter.py` executes command adapters through a cancellable subprocess implementation that can terminate active child processes on timeout or cancellation.
- Tests cover progress output routing, JSON stdout cleanliness, agent-audience suppression, successful per-cell progress, adapter failure progress, timeout/cancellation artifact behavior, and interrupt behavior leaving unfinished cells unreviewed.
- `make check` passes.

## Out of Scope

- Changing review target selection, review cell identity, finding fingerprinting, or finalize semantics.
- Auto-looping until all pending cells are reviewed.
- Implementing distributed workers or background daemon orchestration.
- Changing the external `opencode` CLI behavior itself.
- Automatically lowering the default concurrency or budget; this proposal focuses on observability and cancellation while preserving current defaults.
