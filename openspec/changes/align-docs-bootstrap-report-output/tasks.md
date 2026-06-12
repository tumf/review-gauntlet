## Implementation Tasks

- [ ] Replace mutable `curl | sh` bootstrap behavior in `.wt/setup` with fail-closed behavior or pinned-download-plus-checksum verification. (verification: manual - inspect `.wt/setup` diff and run shell syntax check if available because installer execution should not be performed during tests)
- [ ] Update README Design section to describe the current session lifecycle and external command adapter behavior. (verification: manual - inspect README diff for removed stale “first version only” wording)
- [ ] Update AGENTS smoke commands to use `--format json` for inventory and plan diagnostics. (verification: manual - inspect AGENTS diff and optionally run `uv run review-gauntlet inventory --format json`)
- [ ] Add markdown table-cell escaping or normalization in report rendering. (verification: unit - `uv run pytest tests/test_cli.py` or focused report tests cover pipe and newline values)
- [ ] Run full repository checks after implementation. (verification: integration - `make check`)

## Future Work

- Consider adding a short bootstrap troubleshooting section if contributors frequently lack `prek` locally.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate align-docs-bootstrap-report-output --archive-gate`
