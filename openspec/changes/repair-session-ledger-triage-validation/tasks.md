## Implementation Tasks

- [ ] Make `SessionStore.update_cell_state` validate `rowcount` and raise `LookupError` for unknown session/cell pairs. (verification: unit - `uv run pytest tests/test_session_store.py tests/test_session_reconciliation.py` covers successful and missing-cell updates)
- [ ] Replace `count(*)` finding ID allocation with monotonic max numeric `RGF-*` allocation scoped to the session. (verification: unit - `uv run pytest tests/test_session_store.py tests/test_findings.py` covers non-reuse after gaps)
- [ ] Add regression coverage for fixed-pending findings detected again during a review run so they reopen and are not verified in the same run. (verification: integration - `uv run pytest tests/test_cli_session_review.py` covers redetection and verification ordering)
- [ ] Validate `mark --until` at command input time and return usage errors for malformed dates. (verification: integration - `uv run pytest tests/test_cli_finalize.py tests/test_cli.py` covers valid and invalid `--until`)
- [ ] Handle malformed persisted finding-event metadata in status/finalize without crashing, treating it as a conservative blocker. (verification: integration - `uv run pytest tests/test_cli_finalize.py` injects malformed metadata and verifies actionable blockers)
- [ ] Prevent zero-cell review invocations from creating or updating finalization evidence runs. (verification: integration - `uv run pytest tests/test_cli_session_review.py tests/test_cli_finalize.py` covers zero selected cells and finalize blockers)
- [ ] Run full repository checks after implementation. (verification: integration - `make check`)

## Future Work

- A future bulk-triage proposal may reuse the date validation path introduced here.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate repair-session-ledger-triage-validation --archive-gate`
