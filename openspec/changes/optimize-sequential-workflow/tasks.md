## Implementation Tasks

- [x] Align `status.next_required_action` priority with efficient sequential continuation in `src/review_gauntlet/cli.py` (completion: pending current review cells still return review work first; otherwise reopened, untriaged, confirmed, and fixed-pending finding states are considered before generic stale review work; verification: unit - added CLI status tests in `tests/test_cli_session_review.py` that fail if stale coverage is reported before confirmed or fixed-pending finding work when no pending current cells remain; focused verification passed: `uv run pytest tests/test_cli_session_review.py`).

- [x] Align `review-gauntlet ready` prompt priority with the same continuation ordering (completion: `ready` emits confirmed or fixed-pending continuation prompts before stale review prompts under the same state combinations as `status`; verification: unit - added ready-command tests in `tests/test_cli_session_review.py` that assert prompt selection for stale-plus-confirmed and stale-plus-fixed-pending sessions; focused verification passed: `uv run pytest tests/test_cli_session_review.py`).

- [x] Preserve pending-review precedence and finalize-blocker visibility (completion: pending current cells still produce review work before finding work, and finalization remains blocked while stale coverage, target digest drift, dirty review-universe files, confirmed findings, or fixed-pending findings exist; verification: unit - added tests covering pending-plus-findings priority and finalize blockers remaining present in `status --format json`; focused verification passed: `uv run pytest tests/test_cli_session_review.py`).

- [x] Run focused and full verification (verification: integration - ran `uv run pytest tests/test_cli_session_review.py` and `make check`; completion: focused tests and project checks completed successfully with no unreviewed behavior regressions; not a behavior-bearing implementation task).

## Future Work

- No external approvals or credentials are required.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate optimize-sequential-workflow --archive-gate`

## Acceptance #1 Failure Follow-up
- [x] REGRESSION + spec violation in `ready` (src/review_gauntlet/cli.py:1256-1259): when effective pending review cells coexist with a commit-resolvable dirty blocker, `ready` returns _READY_PROMPTS['finalize'] instead of 'Review pending review cells'. Reproduced via CLI: a --commit-target session with 1 pending cell + an uncommitted non-review file makes `review-gauntlet ready` emit 'Commit intended git changes before finalizing, then finalize...' while `status.next_required_action` correctly stays 'run_review'. Violates openspec/changes/optimize-sequential-workflow/specs/review-sessions/spec.md:15 ('When current review cells are pending, ready SHALL prompt for pending review' AND 'After review-cell and finding continuation work is exhausted, ready SHALL treat dirty...finalize blockers as actionable'), design.md priority (pending #1 before commit-resolvable blockers #7), and the Explicit Completion Condition 'finalize only after all continuation work is exhausted'. Fixed by removing the `_finalize_blockers_include_commit_resolvable` sub-branch so effective pending always returns _READY_PROMPTS['pending_review_cell']; added `test_ready_prioritizes_pending_review_before_dirty_finalize_blocker`; focused verification passed: `uv run pytest tests/test_cli_ready.py tests/test_cli_session_review.py`.
- [x] Spec/implementation mismatch: openspec/changes/optimize-sequential-workflow/specs/review-sessions/spec.md:36 scenario asserts `next_required_action` is `verify_fixes`, but src/review_gauntlet/cli.py:1627 emits `run_verify_fixes` and all tests (tests/test_cli_session_review.py fixed-pending test; tests/test_cli_ready.py:465,516,629) assert `run_verify_fixes`. Fixed by changing the scenario value to `run_verify_fixes` to match the implementation and the confirmed-findings scenario at spec.md:25; focused verification passed: `uv run pytest tests/test_cli_ready.py tests/test_cli_session_review.py`.
