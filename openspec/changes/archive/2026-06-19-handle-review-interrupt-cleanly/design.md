# Design: Handle review interrupt cleanly

## Current Flow

A `KeyboardInterrupt` raised during concurrent review propagates out of `review_cells_concurrently`, through `_cmd_review`, through `_run_session_command`, and past `main()`. Python then prints a traceback and exits as an uncaught exception.

## Target Flow

Review interruption should be represented as an expected command outcome, not an unhandled exception. The review command should own the interrupt boundary, cancel external adapter work, persist any completed results through the dependent result-preservation behavior, emit a structured response, and exit with code `130`.

## Recommended Shape

Use a domain-specific interrupted result or exception inside the review implementation. It should carry enough information for `_cmd_review` to build output without consulting unstable local variables after an abrupt raw interrupt.

Suggested fields:

- `run_id`
- `reviewed_cells`
- `finding_ids`
- `cancelled_cell_ids`
- `failed_cell_id` when a completed failure was observed before interruption
- `interrupted: true`

`_cmd_review` should convert that domain signal into output plus `SystemExit(130)`. Raw `KeyboardInterrupt` should not escape beyond the review command path.

## Output Rules

- JSON mode writes one parseable object to stdout.
- Human mode may write progress and interruption summaries to stderr.
- No mode should print Python traceback text for expected review interruption.

## Compatibility

This does not introduce a new persisted session state. The session remains active and existing `pending`/`reviewed` coverage semantics remain authoritative.
