## Implementation Tasks

- [x] Add an early active-session preflight to the `run` CLI path (completion: `_cmd_run()` calls the session store active-session check before adapter config loading, RunController construction, TUI decision-making, or controller execution; verification: unit - inspect `src/review_gauntlet/cli.py` and add a focused CLI test that monkeypatches config/TUI/controller entry points to prove they are not reached when no active session exists).

- [x] Preserve the existing actionable no-session diagnostic for `run` (completion: invoking `review-gauntlet run` with no `.review-gauntlet/active-session.json` exits with code `1` through the existing `LookupError` handler and writes `no active review session; run review-gauntlet init` to stderr; verification: integration - add or update `tests/test_cli.py` to call `main(["run", str(tmp_path)])` without `init` and assert exit code plus stderr).

- [x] Ensure missing adapter config does not mask the no-session error (completion: a repository with neither an active session nor a local/global run adapter config reports the no-active-session guidance rather than the run adapter configuration error; verification: integration - add a CLI regression test using an isolated temporary repository/root and, if needed, monkeypatched config lookup so the assertion fails if `load_config()` is consulted first).

- [x] Preserve initialized-session run behavior (completion: existing run tests for initialized sessions continue to pass without changing JSON output, TUI behavior, or controller result handling; verification: integration - run focused CLI/run-controller tests such as `uv run pytest tests/test_cli.py tests/test_run_controller.py tests/test_run_tui.py` or the closest existing focused set).

- [x] Run the project quality gate (completion: formatting, linting, type checking, and tests pass using the repository CI-equivalent command; verification: integration - execute `make check` and confirm it exits `0`).

## Future Work

- Consider sharing a small helper for session-command preflight if additional commands need the same before-any-side-effect guarantee.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate guard-run-without-session --archive-gate`
