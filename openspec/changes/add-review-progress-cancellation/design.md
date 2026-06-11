# Design: Review Progress and Cancellation

## Current Behavior

`review-gauntlet review` selects cells, submits adapter work to a `ThreadPoolExecutor`, then waits on futures in selected-cell order. Final output is emitted only after all selected cells have produced results or a failure is processed. The command adapter uses `subprocess.run(..., capture_output=True, timeout=...)`, which does not expose a process handle to the caller while the worker is blocked.

This creates two user-visible issues:

1. Long review runs look stalled because there is no progress output until completion.
2. Interrupting the CLI can still wait for executor shutdown and worker subprocesses.

## Design Goals

- Preserve the one-command-one-run model.
- Preserve deterministic ledger mutation order even if adapter execution is concurrent.
- Keep stdout stable for existing human and JSON final output contracts.
- Make human CLI runs visibly active without requiring log file inspection.
- Make cancellation explicit and safe: unfinished cells remain not reviewed.

## Progress Output Model

Progress is an observation channel, not a result channel. It should write to stderr only. Final summaries continue to use the existing `_emit()` path on stdout.

For human audience runs, progress should include:

- run start summary
- per-cell start
- per-cell success
- per-cell failure or timeout
- cancellation summary when interrupted

For agent audience runs, decorative progress should be suppressed. If future automation needs progress, it should be added as a separate machine-readable event stream in another proposal.

## Concurrency and Ledger Ordering

Adapter execution may remain concurrent, but session ledger writes should continue to happen on the main path in selected-cell order or another explicitly deterministic order. This preserves stable finding order and coverage updates while allowing stderr progress to reflect actual task starts and completions.

## Cancellable Adapter Execution

The command adapter should keep a subprocess handle instead of relying on `subprocess.run()`. A cancellable implementation can use `Popen` plus `communicate(timeout=...)`, write captured stdout/stderr artifacts, and terminate the process on timeout or cancellation.

On POSIX systems, the adapter should prefer process-group/session termination for child cleanup when safe, such as using `start_new_session=True` and terminating the process group. If a graceful termination does not finish within a short bounded period, it should kill the process and record that outcome in `failure.json`.

## Interrupt Handling

The review command should catch `KeyboardInterrupt` around concurrent execution, request cancellation for not-yet-completed work, terminate active command adapter subprocesses where possible, and avoid executor shutdown paths that wait indefinitely. The final state must make incomplete coverage visible rather than optimistic.

## Verification Strategy

- Unit tests cover progress routing and suppression.
- Integration-style CLI tests cover success/failure progress without real external LLM calls.
- Blocking subprocess tests cover timeout/cancellation behavior using local commands.
- Existing session tests continue to prove one-run, budget, concurrency, and failed-cell coverage semantics.
