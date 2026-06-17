## Implementation Tasks

- [ ] Add shared startup-failure classification for subprocess `OSError` cases used by command execution paths. Completion condition: a helper or equivalent logic maps `EMFILE` and `ENFILE` to a resource-exhaustion reason and preserves generic `OSError` details for other startup failures. (verification: unit - tests in `tests/test_command_review_adapter.py` and `tests/test_cli_run.py` assert the failure metadata includes argv, exception type, errno/detail when available, and a resource-exhaustion hint for `errno.EMFILE`.)

- [ ] Convert `CommandReviewAdapter._run_command()` subprocess startup `OSError` into `ReviewAdapterError` instead of allowing raw exceptions to escape. Completion condition: `FileNotFoundError` behavior remains command-not-found specific, while other startup `OSError` failures call the adapter failure path with structured metadata. (verification: unit - `tests/test_command_review_adapter.py` monkeypatches `subprocess.Popen` to raise `OSError(errno.EMFILE, "Too many open files")` and confirms `adapter.review()` raises `ReviewAdapterError` with resource-exhaustion failure details.)

- [ ] Preserve review-run behavior when one selected cell fails from resource exhaustion. Completion condition: `review-gauntlet review --format json` emits a parseable failed-run JSON result with `failed_cell_id` and `failure` details, while successfully completed sibling cells still persist reviewed coverage and findings. (verification: integration - `tests/test_cli_session_review.py` covers a multi-cell run where one adapter startup raises `EMFILE` and another succeeds, proving the command exits non-zero without a final raw traceback and records successful cell progress.)

- [ ] Lower the default review concurrency from `8` to `3` for both review and verify-fixes. Completion condition: `_concurrency_arg()` or equivalent parser wiring in `src/review_gauntlet/cli.py` defaults to `3`, help text displays `default: 3`, and explicit positive `--concurrency` values still override the default. (verification: unit - CLI parser/help tests in `tests/test_cli.py` or `tests/test_cli_session_review.py` assert `review --help` and `verify-fixes --help` show `--concurrency` default `3`; integration - existing or new concurrency tests assert default execution uses no more than three simultaneous adapter tasks when enough cells are selected.)

- [ ] Convert session agent command startup `OSError` into structured run command failure. Completion condition: `_run_session_command_step()` returns `SessionCommandResult(failure={...})` with `reason: startup_error` and resource-exhaustion details for `EMFILE`/`ENFILE`, without constructing a child-process-dependent result. (verification: unit - `tests/test_cli_run.py` or the existing run/session command test module monkeypatches `subprocess.Popen` to raise `OSError(errno.EMFILE, "Too many open files")` and asserts the run result reports structured startup failure instead of raising.)

- [ ] Verify existing command failure semantics remain unchanged. Completion condition: missing command, timeout, cancellation, non-zero exit, and invalid verdict tests continue to pass without expected-output churn unrelated to the new startup-failure shape. (verification: integration - run focused tests for command adapter and run/session behavior, then `make check`.)

## Future Work

- Consider a separate proposal to compute an effective concurrency ceiling from `resource.getrlimit(resource.RLIMIT_NOFILE)` and current open FD usage.
- Consider documenting operational guidance for macOS `ulimit -n` only if repeated user reports show concurrency tuning alone is insufficient.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate handle-subprocess-resource-exhaustion --archive-gate`
