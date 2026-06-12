## Implementation Tasks

- [x] Replace mutable `curl | sh` bootstrap behavior in `.wt/setup` with fail-closed behavior or pinned-download-plus-checksum verification. (verification: manual - inspected repository evidence in `.wt/setup` lines 29-37 showing fail-closed `prek` handling with no remote installer execution; runnable command `sh -n .wt/setup` passed)
- [x] Update README Design section to describe the current session lifecycle and external command adapter behavior. (verification: manual - inspected repository evidence in `README.md:166-180` documenting the stateful coverage workflow and external command adapter support; runnable command `uv run pytest tests/test_cli.py` passed)
- [x] Update AGENTS smoke commands to use `--format json` for inventory and plan diagnostics. (verification: manual - `AGENTS.md` line 17 uses `--format json`; `uv run review-gauntlet inventory . --format json` passed)
- [x] Add markdown table-cell escaping or normalization in report rendering. (verification: unit - `src/review_gauntlet/report.py` lines 6-14 escape pipes, backslashes, and newlines; `uv run pytest tests/test_cli.py` passed with pipe/newline coverage)
- [x] Run full repository checks after implementation. (verification: integration - `agent-exec run -- make check`, job `ad218b1d21e38167e59936cb248dc47c`, exit code 0)

## Future Work

- Consider adding a short bootstrap troubleshooting section if contributors frequently lack `prek` locally.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate align-docs-bootstrap-report-output --archive-gate`

