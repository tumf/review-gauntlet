# Tasks: Review Commit Range

## Implementation Tasks

- [ ] 1. Add `file_digests_at_commit(root, commit)` to `targets.py`. Returns `dict[str, str]` mapping relative paths to SHA256 of `git show <commit>:<path>`. Skips files not present at that commit. verification: unit — `tests/test_targets.py::test_file_digests_at_commit` (new).

- [ ] 2. Store `review_head_commit` in session metadata during `_cmd_init`. Run `git rev-parse HEAD^{commit}` and add to metadata dict at cli.py ~830. verification: unit — `tests/test_cli_session_review.py` — init output includes `review_head_commit`.

- [ ] 3. Use commit digest in `_current_target_cells()` (cli.py). Read `review_head_commit` from `store.session_metadata()`. If present, call `file_digests_at_commit()` instead of `file_digests()`. verification: integration — `tests/test_cli_ready.py` — stale detection with commit digest.

- [ ] 4. Simplify `_effective_current_target_coverage_for_cells` (cli.py ~1840). Remove `fixed_pending_paths` exception from stale condition; keep only `persisted.digest != current.digest`. verification: unit — `tests/test_cli_ready.py::test_status_prioritizes_*` (updated expectations).

- [ ] 5. Simplify `_reconcile_cells` (cli.py ~1314). Remove `fixed_pending_paths` exception from stale condition. verification: unit — `tests/test_cli_session_review.py`.

- [ ] 6. Simplify `_ready_review_cells` (cli.py ~1729). Remove `fixed_pending_paths` exception from stale condition. verification: unit — `tests/test_cli_ready.py`.

- [ ] 7. Remove `store.fixed_pending_paths()` from `session_store.py`. Delete the method; ensure no callers remain. verification: grep — no references to `fixed_pending_paths`.

- [ ] 8. Remove `TargetKind.WORKTREE` from `targets.py`. Remove enum member; update all type annotations and match/case patterns. verification: grep — no references to `TargetKind.WORKTREE` remain in `src/`.

- [ ] 9. Remove `TargetKind.ALL` from `targets.py`. Subsumed by `TargetKind.COMMIT` at `HEAD`; remove enum member. verification: grep — no references to `TargetKind.ALL` remain in `src/`.

- [ ] 10. Update `resolve_target()` to not default to WORKTREE. Remove the default fallthrough that creates a WORKTREE target. verification: unit — `tests/test_targets.py` — updated expectations.

- [ ] 11. Update `_cmd_init` default target logic (cli.py ~818). After checkpoint fallback, fall back to `TargetSpec(kind=COMMIT, commit=HEAD)`. verification: integration — `tests/test_cli_session_review.py` — init default test.

- [ ] 12. Remove `--worktree` CLI argument from init parser. Remove `add_argument("--worktree", ...)` and any associated handling. verification: unit — `tests/test_cli.py` — `--worktree` rejected as unknown flag.

- [ ] 13. Add commit sha to `build_review_prompt` in `review_adapter.py`. Accept optional `review_commit` parameter; include in template variables. verification: unit — `tests/test_review_adapter.py` — prompt lines include commit sha.

- [ ] 14. Add `review_commit` to `_build_file_scoped_ready_prompt` (cli.py). Include in `## Target file` section when session has `review_head_commit`. verification: unit — `tests/test_cli_ready.py` — prompt includes commit sha.

- [ ] 15. Add explicit test that verify-fixes uses working tree digest. `_cmd_verify_fixes` already uses `file_digests(root)`. Add test: uncommitted fix → verify-fixes cell digest ≠ committed review cell digest. verification: integration — `tests/test_cli_verify_fixes.py` — new test.

- [ ] 16. Update all test expectations affected by the change. Stale-related assertions that referenced `fixed_pending_paths` behavior; `test_cli_ready.py`, `test_cli_session_review.py`, `test_run_tui.py`, `test_targets.py`. verification: `make test` — all tests pass.

- [ ] 17. Run full CI: `make check`. verification: manual — format, lint, typecheck, test all pass.

## Future Work

- Automatic git commit after fix step (currently agent must commit manually).
- `TargetSpec.head_mode` reconciliation for new COMMIT-only defaults.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate review-commit-range --archive-gate`
