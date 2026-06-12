## Implementation Tasks

- [x] Replace mutable `curl | sh` bootstrap behavior in `.wt/setup` with fail-closed behavior or pinned-download-plus-checksum verification. (verification: manual - inspected `.wt/setup` diff and ran `sh -n .wt/setup`; installer execution is intentionally not performed during tests)
- [x] Update README Design section to describe the current session lifecycle and external command adapter behavior. (verification: manual - inspected README diff; removed stale “first version only” wording)
- [x] Update AGENTS smoke commands to use `--format json` for inventory and plan diagnostics. (verification: manual - inspected AGENTS diff and ran `uv run review-gauntlet inventory . --format json`)
- [x] Add markdown table-cell escaping or normalization in report rendering. (verification: unit - `uv run pytest tests/test_cli.py` covers pipe and newline values; 24 passed)
- [x] Run full repository checks after implementation. (verification: integration - `agent-exec run -- make check`, job `ad218b1d21e38167e59936cb248dc47c`, exit code 0)

## Future Work

- Consider adding a short bootstrap troubleshooting section if contributors frequently lack `prek` locally.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate align-docs-bootstrap-report-output --archive-gate`
