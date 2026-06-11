## Implementation Tasks

- [ ] Enrich invalid verdict JSON failures in `src/review_gauntlet/review_adapter.py` with `output_mode`, `verdict_path`, `raw_verdict_path`, a bounded `raw_snippet`, and a concise strict-JSON hint. (verification: unit - add `tests/test_review_adapter.py::test_invalid_file_json_failure_includes_actionable_diagnostics` and assert the persisted `failure.json` contains those fields)
- [ ] Propagate enriched invalid-verdict failure metadata through `ReviewAdapterError.failure` to `review-gauntlet review` failure output. (verification: integration - add `tests/test_cli.py` coverage using a malformed verdict fixture or command adapter and assert the CLI `failure` field includes the diagnostic keys)
- [ ] Preserve hard-failure coverage semantics for malformed verdicts. (verification: integration - assert via `SessionStore.list_cells` in `tests/test_cli.py` or `tests/test_init_targets.py` that the failed malformed-verdict cell remains pending or stale and is not marked reviewed)
- [ ] Cover malformed `stdout-json` adapter output with equivalent diagnostics. (verification: unit - add `tests/test_review_adapter.py::test_invalid_stdout_json_failure_includes_actionable_diagnostics` using adapter output mode `stdout-json`)
- [ ] Preserve valid verdict behavior. (verification: integration - keep existing valid command adapter tests passing and add an assertion that valid verdicts still write normalized `verdict.json`)
- [ ] Keep JSON repair out of runtime behavior. (verification: unit - malformed single-quoted verdict in `tests/test_review_adapter.py` must fail rather than be accepted or normalized)
- [ ] Run the project check suite. (verification: manual - run `make check` from `/Users/tumf/work/review-gauntlet` and record that it passes)

## Future Work

- Consider a separate proposal for explicit retry ergonomics for only failed cells.
- Consider a separate proposal for a machine-readable artifact inspection command if users need to inspect adapter failures without reading files directly.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate improve-invalid-verdict-diagnostics --archive-gate`
