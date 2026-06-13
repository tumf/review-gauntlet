## Implementation Tasks

- [x] Add status regression coverage for pending cells plus confirmed findings (verification: unit - `uv run pytest tests/test_cli_ready.py -k status`; completion: a test constructs an active session with at least one pending review cell and one confirmed finding, then asserts `status.next_required_action == "run_review"` and both blocker classes are present).

- [x] Add status regression coverage for stale cells plus confirmed findings (verification: unit - `uv run pytest tests/test_cli_ready.py -k status`; completion: a test constructs an active session with at least one stale review cell and one confirmed finding, then asserts `status.next_required_action == "run_review"` and both blocker classes are present).

- [x] Keep or repair deterministic status next-action ordering (verification: unit - `uv run pytest tests/test_cli_ready.py tests/test_cli_session_review.py`; completion: `src/review_gauntlet/cli.py` checks pending/stale review-cell counts before any finding-state action and returns `run_review` for incomplete coverage).

- [x] Keep or repair ready prompt precedence for incomplete coverage with confirmed findings (verification: unit - `uv run pytest tests/test_cli_ready.py -k ready`; completion: `review-gauntlet ready --format json` returns a review-coverage prompt, not a confirmed-finding fix prompt, when pending or stale review cells exist alongside confirmed findings).

- [x] Run repository quality gates (verification: integration - `make check`; completion: formatting, linting, type checking, and tests all pass from the repository root).

## Future Work

- External orchestrators should update to a package version containing this regression coverage before relying on `next_required_action` ordering in long-running review sessions.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate enforce-status-coverage-priority --archive-gate`
