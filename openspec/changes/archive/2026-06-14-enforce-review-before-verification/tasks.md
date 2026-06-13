## Implementation Tasks

- [x] Add status regression coverage for pending cells plus fixed-pending findings (verification: unit - `uv run pytest tests/test_cli_ready.py -k status`; completion: a test constructs an active session with pending review cells and `fixed_pending_verification` findings, then asserts `next_required_action == "run_review"` and blocker visibility for both coverage and verification).

- [x] Add status regression coverage for stale cells plus fixed-pending findings (verification: unit - `uv run pytest tests/test_cli_ready.py -k status`; completion: a test constructs an active session with stale review cells and `fixed_pending_verification` findings, then asserts `next_required_action == "run_review"` and blocker visibility for both stale coverage and verification).

- [x] Add status regression coverage for target digest drift plus fixed-pending findings (verification: unit - `uv run pytest tests/test_cli_ready.py -k status`; completion: a test constructs a session with current cells not marked stale but with target digest drift and `fixed_pending_verification` findings, then asserts `next_required_action == "run_review"`).

- [x] Keep or repair deterministic next-action ordering before verification work (verification: unit - `uv run pytest tests/test_cli_ready.py tests/test_cli_session_review.py`; completion: `_next_action` checks pending/stale coverage and target digest drift before `fixed_pending_verification` and returns `run_review` for those cases).

- [x] Keep or repair ready prompt precedence before verification work (verification: unit - `uv run pytest tests/test_cli_ready.py -k ready`; completion: `review-gauntlet ready --format json` returns a review-oriented prompt instead of a verify-fixes prompt whenever incomplete coverage or target digest drift coexists with fixed-pending findings).

- [x] Preserve verification as next action when coverage is current (verification: unit - `uv run pytest tests/test_cli_ready.py tests/test_cli_session_review.py`; completion: existing tests or a new regression test show `run_verify_fixes` remains selected when there are fixed-pending findings and no coverage/digest blockers).


- [x] Run repository quality gates (verification: integration - `make check`; completion: formatting, linting, type checking, and tests all pass from the repository root).

## Future Work

- Downstream projects running older packaged versions should update to a version containing this fix before trusting `next_required_action` in sessions that combine stale coverage with fixed-pending findings.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate enforce-review-before-verification --archive-gate`
