## Implementation Tasks

- [x] Add the `verify-fixes` parser surface and command routing in `src/review_gauntlet/cli.py`, including `--config`, `--fixture`, `--budget`, `--concurrency`, `--format`, `--audience`, repeatable `--finding`, and repeatable `--path`. (verification: unit - parser/help assertions in `tests/test_cli.py` or `tests/test_cli_verify_fixes.py` prove the new command accepts supported options and rejects obsolete/unsafe options)
- [x] Implement fixed-pending finding selection and filtering against the active session without mutating state before adapter execution. (verification: integration - `tests/test_cli_verify_fixes.py` creates mixed finding states and proves `verify-fixes` targets only `fixed_pending_verification` findings, with `--finding` and `--path` filters applying deterministically)
- [x] Wire verification cell selection to current review cells for the active target, respecting `--budget` and excluding unrelated pending, stale, confirmed, untriaged, reopened, and terminal findings. (verification: integration - `tests/test_cli_verify_fixes.py` fixture tests prove unrelated cells are not invoked and `--budget 0` creates no run or finding events)
- [x] Reuse the existing review adapter execution path for selected verification cells, including command config loading, fixture mode, progress reporting, concurrency, cancellation, prompt artifacts, output parsing, and verdict validation. (verification: integration - `tests/test_cli_verify_fixes.py` command-adapter or fixture tests assert `.review-gauntlet/runs/<run_id>/cells/<cell_id>/` artifacts are created for selected cells and adapter failures surface in the `verify-fixes` result)
- [x] Record verification outcomes through existing finding transition rules: absent targeted fingerprints on successfully evaluated paths transition to `fixed_verified`; re-detected targeted fingerprints transition to `reopened`; failed or unevaluated targeted findings remain `fixed_pending_verification`. (verification: integration - `tests/test_cli_verify_fixes.py` inspects `findings` and `finding_events` rows in `.review-gauntlet/ledger.sqlite` after success, redetection, and partial failure scenarios)
- [x] Define and emit the `verify-fixes` result payload for text and JSON formats, including `run_id`, `reviewed_cells`, `targeted_finding_ids`, `fixed_verified_ids`, `reopened_ids`, `unverifiable_ids`, `finding_ids`, `can_finalize`, and `finalize_blockers`. (verification: integration - `tests/test_cli_verify_fixes.py` parses stdout directly and asserts result shape and exit codes for success, no-op, reopened, and failure paths)
- [x] Apply repository-relative path safety to `--path` using the same semantics as `findings --path`, rejecting absolute paths and parent traversal before adapter execution. (verification: unit - `tests/test_cli_verify_fixes.py` unsafe path tests assert exit code `64` and unchanged run/event counts in `.review-gauntlet/ledger.sqlite`)
- [x] Update `README.md` command guidance to document `mark ... fixed` followed by `verify-fixes` as the post-fix re-review workflow. (verification: manual - inspect `README.md` and confirm it contains `uv run review-gauntlet verify-fixes --config review-gauntlet.jsonc` in the post-fix command sequence and does not document deprecated flags)
- [x] Run repository verification for the implemented change. (verification: manual - `make check` passes; if too slow or environment-blocked, record the exact failing command/output for follow-up)

## Future Work

- CI or notification orchestration that waits for developers to fix findings and then invokes `verify-fixes` automatically is intentionally external to review-gauntlet.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-verify-fixes-command --archive-gate`.
