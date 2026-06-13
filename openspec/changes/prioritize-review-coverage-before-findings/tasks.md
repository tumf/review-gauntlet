## Implementation Tasks

- [x] Update status next-action priority in `src/review_gauntlet/cli.py` so pending or stale review cells return `run_review` before live finding states are considered. (verification: unit - add or update `tests/test_cli_ready.py` or `tests/test_cli_session_review.py` assertions that pending cells plus untriaged findings produce `next_required_action == "run_review"`)
- [x] Update ready prompt priority in `src/review_gauntlet/cli.py` so pending or stale review cells produce review prompts before reopened, untriaged, confirmed, or fixed-pending finding prompts. (verification: unit - update `tests/test_cli_ready.py::test_ready_priority_order_is_deterministic` and add a mixed pending/finding prompt assertion)
- [x] Preserve finding workflow reachability after coverage is complete by testing that untriaged/reopened, confirmed, and fixed-pending findings still produce their current actions/prompts once all review cells are reviewed. (verification: unit - assertions in `tests/test_cli_ready.py` cover the post-coverage finding priority sequence)
- [x] Preserve conservative finalize blocker reporting when both pending cells and untriaged findings exist. (verification: unit - JSON status assertion includes both `review cells are still pending` and `findings remain untriaged` while next action is `run_review`)
- [x] Run the project quality gate. (verification: integration - `make check` passes)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate prioritize-review-coverage-before-findings --archive-gate`
