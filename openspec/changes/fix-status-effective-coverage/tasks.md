## Implementation Tasks

- [ ] Implement an effective coverage computation helper for active-session status that compares current target cells from `src/review_gauntlet/cli.py` with persisted `review_cells` rows without writing to the ledger (verification: unit - focused pytest covers helper behavior through `review-gauntlet status --format json`).
- [ ] Wire `review-gauntlet status` to use effective current-target coverage for the public `coverage` field and for `next_required_action`/finalize blocker decisions where coverage state is evaluated (verification: integration - `uv run pytest tests/test_cli_ready.py -k status`).
- [ ] Preserve read-only status behavior by ensuring `status` does not insert review cells, update cell states, create runs, update findings, write checkpoints, or change active-session metadata (verification: integration - `uv run pytest tests/test_cli_ready.py -k status`, with a regression test snapshotting `.review-gauntlet/ledger.sqlite` and checkpoint files before and after `status`).
- [ ] Add regression coverage for a reviewed current cell whose content digest changes so `status.coverage` reports stale instead of reviewed and the next action remains actionable (verification: integration - new or updated test in `tests/test_cli_ready.py`).
- [ ] Add regression coverage for a current target cell missing from persisted `review_cells` so `status.coverage` reports pending review work without mutating persisted cells (verification: integration - new or updated test in `tests/test_cli_ready.py`).
- [ ] Add or preserve regression coverage for whole-target digest drift where all current target cells are present, reviewed, and digest-matching so `status` does not force review solely because of target digest drift (verification: integration - existing `tests/test_cli_ready.py` digest-drift test remains passing).
- [ ] Run project checks after implementation (verification: integration - `make check`).

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate fix-status-effective-coverage --archive-gate`
