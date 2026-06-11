## Implementation Tasks

- [x] Add CLI option parsing for `review --concurrency` with default `8` and positive-integer validation (completion: `build_parser()` exposes the option only on the `review` command, and invalid values less than `1` exit with usage error before adapter work starts; verification: unit - add/extend `tests/test_cli_session_review.py` to assert `--concurrency 0` fails with exit code `64` and does not mark cells reviewed).

- [x] Refactor review-cell selection into a deterministic pre-execution selection step that respects current eligibility and `--budget` (completion: `_cmd_review()` or a helper builds the current cell map once after reconciliation, selects cells in the existing session row order, and selects at most `args.budget` cells before starting adapter execution; verification: unit - add/extend `tests/test_cli_session_review.py` to assert `--budget 1 --concurrency 8` reviews exactly one cell and leaves additional eligible cells pending).

- [x] Execute selected adapter reviews concurrently up to the configured concurrency while keeping ledger mutations deterministic (completion: adapter calls for selected cells are bounded by the configured concurrency, but finding normalization, finding upserts, cell state updates, fixed-finding verification, and emitted `finding_ids` are applied in selected-cell order from the main control path; verification: integration - add a command-adapter test in `tests/test_cli_session_review.py` that uses multiple eligible cells and a fixture or helper command to prove more than one selected cell is reviewed in a single run with `--concurrency 2`).

- [x] Preserve existing failure semantics under concurrent execution (completion: if any selected adapter review fails, the reported `failed_cell_id`, `error`, `failure`, `reviewed_cells`, and status fields match the existing JSON failure contract, and the failed cell is not marked `reviewed`; verification: integration - add/extend `tests/test_cli_session_review.py` with multiple selected cells where one adapter invocation fails and assert the failed cell remains pending/stale while successful committed cells retain reviewed coverage).

- [x] Preserve command-adapter artifact isolation for concurrent cell reviews (completion: each concurrently reviewed cell still writes prompt, stdout, stderr, command metadata, and verdict artifacts under its own `.review-gauntlet/runs/<run_id>/cells/<cell_id>/` directory without shared output-file collisions; verification: integration - inspect per-cell artifact paths in an existing or new command-adapter test after a concurrent review run).

- [x] Update user-facing documentation for `review --concurrency` (verification: manual - intentionally documentation-focused coverage, compare `README.md` or CLI usage documentation against `uv run review-gauntlet review --help` output; completion: README or CLI usage documentation describes `--concurrency`, its default, its relation to `--budget`, and that it does not automatically pass concurrency to nested adapter commands).

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-review-concurrency --archive-gate`

Implementation verification should run the project CI-equivalent command: `make check`.
