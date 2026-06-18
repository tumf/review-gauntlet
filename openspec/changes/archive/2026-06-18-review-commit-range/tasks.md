# Tasks: Review Commit Range

## Implementation Tasks

- [x] 1. Add `file_digests_at_commit(root, commit)` to `targets.py`. Returns `dict[str, str]` mapping relative paths to SHA256 of `git show <commit>:<path>`. Skips files not present at that commit. verification: unit — `tests/test_targets.py::test_file_digests_at_commit` (new).

- [x] 2. Store `review_head_commit` in session metadata during `_cmd_init`. Run `git rev-parse HEAD^{commit}` and add to metadata dict at cli.py ~830. verification: unit — `tests/test_cli_session_review.py` — init output includes `review_head_commit`.

- [x] 3. Use commit digest in `_current_target_cells()` (cli.py). Read `review_head_commit` from `store.session_metadata()`. If present, call `file_digests_at_commit()` instead of `file_digests()`. verification: integration — `tests/test_cli_ready.py` — stale detection with commit digest.

- [x] 4. Simplify `_effective_current_target_coverage_for_cells` (cli.py ~1840). Remove `fixed_pending_paths` exception from stale condition; keep only `persisted.digest != current.digest`. verification: unit — `tests/test_cli_ready.py::test_status_prioritizes_*` (updated expectations).

- [x] 5. Simplify `_reconcile_cells` (cli.py ~1314). Remove `fixed_pending_paths` exception from stale condition. verification: unit — `tests/test_cli_session_review.py`.

- [x] 6. Simplify `_ready_review_cells` (cli.py ~1729). Remove `fixed_pending_paths` exception from stale condition. verification: unit — `tests/test_cli_ready.py`.

- [x] 7. Remove `store.fixed_pending_paths()` from `session_store.py`. Delete the method; ensure no callers remain. verification: grep — no references to `fixed_pending_paths`.

- [x] 8. Remove `TargetKind.WORKTREE` from `targets.py`. Remove enum member; update all type annotations and match/case patterns. verification: grep — no references to `TargetKind.WORKTREE` remain in `src/`.

- [x] 9. Remove `TargetKind.ALL` from `targets.py`. Subsumed by `TargetKind.COMMIT` at `HEAD`; remove enum member. verification: grep — no references to `TargetKind.ALL` remain in `src/`.

- [x] 10. Update `resolve_target()` to not default to WORKTREE. Remove the default fallthrough that creates a WORKTREE target. verification: unit — `tests/test_targets.py` — updated expectations.

- [x] 11. Update `_cmd_init` default target logic (cli.py ~818). After checkpoint fallback, fall back to `TargetSpec(kind=COMMIT, commit=HEAD)`. verification: integration — `tests/test_cli_session_review.py` — init default test.

- [x] 12. Remove `--worktree` CLI argument from init parser. Remove `add_argument("--worktree", ...)` and any associated handling. verification: unit — `tests/test_cli.py` — `--worktree` rejected as unknown flag.

- [x] 13. Add commit sha to `build_review_prompt` in `review_adapter.py`. Accept optional `review_commit` parameter; include in template variables. verification: unit — `tests/test_review_adapter.py` — prompt lines include commit sha.

- [x] 14. Add `review_commit` to `_build_file_scoped_ready_prompt` (cli.py). Include in `## Target file` section when session has `review_head_commit`. verification: unit — `tests/test_cli_ready.py` — prompt includes commit sha.

- [x] 15. Add explicit test that verify-fixes uses working tree digest. `_cmd_verify_fixes` already uses `file_digests(root)`. Add test: uncommitted fix → verify-fixes cell digest ≠ committed review cell digest. verification: integration — `tests/test_cli_verify_fixes.py` — new test.

- [x] 16. Update all test expectations affected by the change. Stale-related assertions that referenced `fixed_pending_paths` behavior; `test_cli_ready.py`, `test_cli_session_review.py`, `test_run_tui.py`, `test_targets.py`. verification: `make test` — all tests pass.

- [x] 17. Run full CI: `make check`. (verification: manual — `make check` passes, covering format-check, lint, typecheck, and test.)

## Future Work

- Automatic git commit after fix step (currently agent must commit manually).
- `TargetSpec.head_mode` reconciliation for new COMMIT-only defaults.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate review-commit-range --archive-gate`
