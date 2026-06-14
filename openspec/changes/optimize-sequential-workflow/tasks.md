## Implementation Tasks

- [ ] Align `status.next_required_action` priority with efficient sequential continuation in `src/review_gauntlet/cli.py` (completion: pending current review cells still return review work first; otherwise reopened, untriaged, confirmed, and fixed-pending finding states are considered before generic stale review work; verification: unit - add or update CLI status tests in `tests/test_cli_session_review.py` that fail if stale coverage is reported before confirmed or fixed-pending finding work when no pending current cells remain).

- [ ] Align `review-gauntlet ready` prompt priority with the same continuation ordering (completion: `ready` emits confirmed or fixed-pending continuation prompts before stale review prompts under the same state combinations as `status`; verification: unit - add or update ready-command tests in `tests/test_cli_session_review.py` that assert prompt selection for stale-plus-confirmed and stale-plus-fixed-pending sessions).

- [ ] Preserve pending-review precedence and finalize-blocker visibility (completion: pending current cells still produce review work before finding work, and finalization remains blocked while stale coverage, target digest drift, dirty review-universe files, confirmed findings, or fixed-pending findings exist; verification: unit - add or update tests covering pending-plus-findings priority and finalize blockers remaining present in `status --format json`).

- [ ] Run focused and full verification (verification: integration - run `uv run pytest tests/test_cli_session_review.py` and `make check`; completion: focused tests and project checks complete successfully with no unreviewed behavior regressions; not a behavior-bearing implementation task).

## Future Work

- No external approvals or credentials are required.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate optimize-sequential-workflow --archive-gate`
