# Design: structured subprocess startup failures

## Current Behavior

`review_cells_concurrently()` schedules review cells on a thread pool. For command-backed reviews, each cell enters `CommandReviewAdapter._run_command()` and starts an external command with stdout and stderr pipes. If pipe creation fails before the child process exists, Python raises `OSError` from `subprocess.Popen()`.

The current adapter startup handler only catches `FileNotFoundError`. Other `OSError` subclasses and instances can escape the adapter path, producing a generic unexpected exception or raw traceback instead of a domain-specific failure.

`_run_session_command_step()` has the same startup gap for run-agent command execution.

## Decision

Add explicit subprocess startup error classification at the command execution boundary.

- Missing executable remains a command-not-found startup error.
- `errno.EMFILE` and `errno.ENFILE` become resource-exhaustion startup failures.
- Other `OSError` startup failures become structured startup failures with the original exception details.

Also lower the default review/verify-fixes concurrency from `8` to `3`. This reduces default subprocess pipe fan-out without removing the user's ability to opt into higher explicit concurrency.

This keeps review-gauntlet aligned with the constitution: failed and unknown review work remains visible, retryable, and represented in structured state.

## Why not auto-clamp concurrency now

Automatic clamping based on file descriptor limits may be useful, but it changes runtime scheduling semantics and can surprise users who explicitly set `--concurrency`. It also needs platform-specific handling and observability for requested versus effective concurrency.

This proposal intentionally makes the failure legible first. A later proposal can add adaptive concurrency with clearer product behavior.

## Verification Strategy

Tests should inject startup failures by monkeypatching `subprocess.Popen`, not by exhausting real file descriptors. Real FD exhaustion is slow, flaky, and host-dependent. Monkeypatching proves the command boundary handles the OS error deterministically while keeping the default test suite under the repository's speed expectations.
