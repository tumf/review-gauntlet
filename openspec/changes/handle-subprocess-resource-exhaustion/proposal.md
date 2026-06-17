---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/review_adapter.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/checkpoint.py
  - src/review_gauntlet/targets.py
  - tests/test_command_review_adapter.py
  - tests/test_cli_session_review.py
---

# Handle subprocess resource exhaustion as structured failures

**Change Type**: implementation

## Premise / Context

- A reported crash shows `OSError: [Errno 24] Too many open files` while Python is creating subprocess pipes for `['git', 'diff', '--name-only', '--cached']`.
- `review-gauntlet review` and `verify-fixes` run selected review cells concurrently through `review_cells_concurrently()` with current default `--concurrency 8` and a hard cap of 64.
- The requested behavior now includes lowering the CLI default concurrency to `3` to reduce subprocess pipe fan-out on typical macOS developer environments.
- `CommandReviewAdapter._run_command()` starts external review commands with `stdout=PIPE` and `stderr=PIPE`, but only handles `FileNotFoundError` during process startup.
- Session agent command startup in `cli.py` uses the same pipe pattern and also only handles `FileNotFoundError`.
- The project constitution requires failed and unknown states to remain visible, and review commands must record explicit structured state rather than hide incompleteness behind raw failures.

## Problem/Context

When the process open-file limit is exhausted, subprocess startup can fail before a child process exists. Today that startup `OSError` can escape as a raw traceback or be wrapped as a generic unexpected adapter exception. The developer sees Python internals instead of actionable review-gauntlet state, and the failed review cell is not clearly classified as retryable resource exhaustion.

This is especially likely during concurrent review because each external command reserves parent-side stdout/stderr pipes, and the adapter command may itself run nested commands such as `git diff --name-only --cached`.

## Proposed Solution

Treat subprocess startup `OSError` failures as structured command-startup failures across review adapter and session command execution.

For resource exhaustion errors such as `EMFILE` and `ENFILE`, classify the failure distinctly and provide guidance to reduce `--concurrency` or raise the process open-file limit. Preserve existing `FileNotFoundError` behavior for missing commands.

Lower the default `--concurrency` for review and verify-fixes from `8` to `3`, and update parser help/spec expectations accordingly. Explicit user-provided concurrency values remain supported and bounded by the existing positive-integer validation and worker cap.

Do not implement automatic concurrency clamping in this change. The fix is to make the failure explicit, parseable, retryable, and non-traceback-producing while using a safer default fan-out.

## Acceptance Criteria

- `CommandReviewAdapter` converts subprocess startup `OSError` into `ReviewAdapterError` failure details instead of leaking a raw traceback.
- `EMFILE` and `ENFILE` startup failures include a distinct resource-exhaustion reason and actionable hint.
- `review-gauntlet review --format json` reports a failed cell with structured failure details when adapter startup hits `EMFILE`, while successful cells in the same run still record normally.
- Session agent command startup in `review-gauntlet run` converts subprocess startup `OSError` into a structured `startup_error` result instead of raising a raw traceback.
- `review-gauntlet review --help` and `review-gauntlet verify-fixes --help` show `--concurrency` defaulting to `3`.
- Invoking review or verify-fixes without an explicit `--concurrency` uses at most three simultaneous adapter review tasks, subject to selected-cell count and budget.
- Existing `FileNotFoundError`, timeout, cancellation, non-zero command behavior, and explicit positive `--concurrency` values remain unchanged.

## Explicit Completion Conditions

- `src/review_gauntlet/review_adapter.py` handles subprocess startup `OSError` and emits structured failure metadata containing at least the argv, exception type, errno when available, detail text, and a resource-exhaustion reason/hint for `EMFILE` or `ENFILE`.
- `src/review_gauntlet/cli.py` handles session command startup `OSError` in `_run_session_command_step()` and returns a `SessionCommandResult` failure rather than raising.
- `src/review_gauntlet/cli.py` sets the parser default and help text for review/verify-fixes `--concurrency` to `3`.
- Regression tests monkeypatch subprocess startup to raise `OSError(errno.EMFILE, "Too many open files")` and verify parseable failure output for both review adapter and run/session command paths.
- CLI/help tests verify the new concurrency default is visible and effective.
- `make check` passes after implementation.

## Out of Scope

- Automatically lowering `--concurrency` based on `RLIMIT_NOFILE`.
- Changing the maximum allowed explicit concurrency cap.
- Changing git status/diff subprocess behavior in checkpoint or target discovery beyond preserving current structured handling.
- Modifying source code as part of this proposal creation step.
