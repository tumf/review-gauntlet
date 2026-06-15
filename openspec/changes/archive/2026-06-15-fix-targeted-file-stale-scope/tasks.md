## Implementation Tasks

- [x] Add file-path digest refresh support to the session store. Completion condition: `SessionStore` can update `content_digest` for all cells in a session with a given `file_path` while preserving each row's `state`, `rule_id`, `slice_id`, and `cell_id`. (verification: unit - `uv run pytest tests/test_session_reconciliation.py` or a focused store test fails if sibling states are mutated or unknown session/path handling silently corrupts rows.)
- [x] Refresh targeted-file sibling freshness after successful `review` cell evaluation. Completion condition: after a successful selected cell in `review`, all cells with the same `file_path` have the current file digest, selected cells are marked `reviewed`, and unselected siblings keep their prior states. (verification: integration - `uv run pytest tests/test_session_reconciliation.py::test_review_refreshes_targeted_file_siblings_without_staling_them` or equivalent.)
- [x] Refresh targeted-file sibling freshness after successful `verify-fixes` cell evaluation. Completion condition: after `verify-fixes` successfully evaluates a fixed-pending finding path, all cells with that same `file_path` have the current file digest while only selected verification cells record reviewed coverage. (verification: integration - `uv run pytest tests/test_cli_verify_fixes.py::test_verify_fixes_refreshes_targeted_file_siblings_without_staling_them` or equivalent.)
- [x] Preserve stale coverage for incidental changed files. Completion condition: if `file1` is the successful fix/verify target and `file2` is also modified incidentally, `file1` cells are not stale while reviewed cells for `file2` are stale and finalization remains blocked by stale review cells. (verification: integration - `uv run pytest tests/test_session_reconciliation.py::test_incidental_changed_file_stales_while_target_file_siblings_do_not` or equivalent.)
- [x] Preserve sibling state semantics during targeted digest refresh. Completion condition: targeted-file siblings that are `pending` remain `pending`, siblings that are `stale` are not silently promoted to `reviewed`, and only successfully selected cells are marked reviewed by review execution. (verification: integration - `uv run pytest tests/test_session_reconciliation.py` includes mixed-state targeted-file fixtures.)
- [x] Preserve existing verify-fixes targeting and error behavior. Completion condition: `verify-fixes` still limits adapter execution to matching fixed-pending findings, keeps unverifiable findings visible on failures, and maintains structured JSON output. (verification: integration - `uv run pytest tests/test_cli_verify_fixes.py`.)
- [x] Run focused verification and the full repository quality gate. Completion condition: stale-scope focused tests pass and formatting, linting, strict type checking, and tests all pass. (verification: integration - `uv run pytest tests/test_session_reconciliation.py tests/test_cli_verify_fixes.py` and `make check`.)

## Future Work

- Consider a later schema refactor that separates file freshness snapshots from per-cell coverage state if additional freshness dimensions are needed.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate. Expected archive gate: `cflx openspec validate fix-targeted-file-stale-scope --archive-gate`.
