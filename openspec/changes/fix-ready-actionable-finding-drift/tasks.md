## Implementation Tasks

- [x] Make ready finding prompt selection data-consistent by deriving each actionable finding bucket from the materialized `_ready_findings()` result before calling the file-scoped prompt builder. (verification: unit - `uv run pytest tests/test_cli_ready.py::test_ready_skips_empty_finding_bucket_without_traceback`; completion condition: the test demonstrates an actionable aggregate count cannot force `_first_file_path_from_findings()` with an empty tuple)
- [x] Preserve ready prompt priority for valid materialized work after the data-consistency change. (verification: unit - `uv run pytest tests/test_cli_ready.py::test_ready_priority_order_is_deterministic tests/test_cli_ready.py::test_ready_prioritizes_confirmed_findings_before_stale_review`; completion condition: priority assertions still select the same prompt categories for real review cells/findings)
- [x] Prevent `review-gauntlet run` command handling from masking primary run/ready failures with `TypeError` when `_cmd_run()` does not return a result dictionary. (verification: unit - `uv run pytest tests/test_cli_run.py::test_run_does_not_mask_primary_exception_with_none_result`; completion condition: the observed exception or structured failure is not a `NoneType` subscript error)
- [x] Keep same-prompt handoff from `ready` to `run` unchanged for normal file-scoped tasks. (verification: integration - `uv run pytest tests/test_cli_run.py::test_run_passes_same_prompt_as_ready_and_completes_when_active_session_removed tests/test_cli_session_review.py::test_run_passes_same_file_scoped_prompt_as_ready`; completion condition: run still passes exactly the ready-generated prompt to the configured command adapter)
- [x] Run full repository validation after the focused regression tests pass. (verification: integration - `make check`; completion condition: format, lint, typecheck, and test targets all exit 0)

## Future Work

- Add ledger-repair commands only if future investigations find durable corrupted state that cannot be safely skipped or surfaced by ready/status.

## Final Validation

Expected implementation validation: `make check`.
Expected proposal validation: `cflx openspec validate fix-ready-actionable-finding-drift --strict --evidence warn`.
Expected archive gate: `cflx openspec validate fix-ready-actionable-finding-drift --archive-gate`.
