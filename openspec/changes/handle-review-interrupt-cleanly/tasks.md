## Implementation Tasks

- [x] Introduce a domain-level interrupted review outcome or exception in `src/review_gauntlet/cli.py` that carries partial review summary data without leaking raw `KeyboardInterrupt` to `main()`. (verification: unit - add or update `tests/test_review_progress.py` interrupt tests to assert summary fields are available without raising raw `KeyboardInterrupt` past the review boundary)
- [x] Update `_cmd_review` or the CLI boundary in `src/review_gauntlet/cli.py` to emit structured interrupted output for `--format json`. (verification: integration - add a CLI test in `tests/test_review_progress.py` or `tests/test_cli_session_review.py` that captures stdout, parses JSON, and asserts `interrupted: true`, `run_id`, `reviewed_cells`, and status fields)
- [x] Return exit code `130` for interrupted review commands. (verification: integration - add a CLI test in `tests/test_review_progress.py` that invokes review through an entrypoint path and observes `SystemExit(130)`)
- [x] Suppress raw Python traceback output for review interrupts while retaining concise human progress messages. (verification: integration - add a CLI test in `tests/test_review_progress.py` that captures stderr and asserts `Traceback` is absent)
- [x] Preserve `CommandReviewAdapter.cancel()` and `cancel_adapter(...)` behavior during clean interrupt handling. (verification: unit - update the fake cancellable adapter test in `tests/test_review_progress.py` to assert `cancel()` is invoked)
- [x] Verify active session retryability after clean interrupt. (verification: integration - add a CLI test in `tests/test_cli_session_review.py` that asserts `SessionStore.active_session_id()` still returns the interrupted session)
- [x] Run repository checks. (verification: integration - `make check`)

## Future Work

- Shell-specific signal behavior outside Python-level `KeyboardInterrupt` handling is deferred unless local tests expose a review-specific gap.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate handle-review-interrupt-cleanly --archive-gate`
