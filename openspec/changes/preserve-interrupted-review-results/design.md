# Design: Preserve interrupted review results

## Current Flow

`_cmd_review` creates a run, invokes `review_cells_concurrently`, then iterates over all selected cells and persists outcomes. `review_cells_concurrently` owns the futures and local `results` dictionary. A `KeyboardInterrupt` raised while waiting in `as_completed` aborts before `_cmd_review` receives those results.

## Target Flow

Review execution should separate two responsibilities:

1. Concurrent adapter execution and cancellation.
2. Durable per-cell persistence.

The concurrency layer should notify `_cmd_review` whenever a cell outcome is available. `_cmd_review` should persist successful outcomes immediately and record failures for structured reporting. On interrupt, the concurrency layer should cancel unfinished work but first drain completed futures that can be read without blocking.

## Recommended Shape

Introduce either:

- a per-result callback such as `on_result(cell, outcome)`, called from the main thread while consuming futures; or
- a small result stream/summary object that exposes outcomes incrementally and returns an interrupted summary.

The callback approach is preferred because SQLite writes remain serialized in the command thread and no worker thread needs direct store access.

## Persistence Rules

- Successful `ReviewAdapterResult`: normalize comments, upsert findings, refresh file digest, mark cell reviewed.
- `ReviewAdapterError`: keep cell pending and report first failure as today.
- Interrupted unfinished cell: keep pending.
- Completed future discovered during interrupt: process using the same success/error path as a normal completed future.

## Concurrency Rules

- Do not block on unfinished futures during interrupt handling.
- Call `cancel_adapter(adapter)` once when interrupted.
- Cancel pending futures after completed futures are drained.
- Shut down the executor with `wait=False` or equivalent non-blocking behavior for interrupted runs.

## Trade-offs

Incremental persistence means a run can have a partial durable result set when interrupted. This matches existing semantics for partial adapter failure and the constitution principle that unknown work remains visible rather than hidden.
