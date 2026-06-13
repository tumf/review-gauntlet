---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - tests/test_cli_ready.py
---

# Enforce review work before fix verification

**Change Type**: implementation

## Problem / Context

A live `review-gauntlet status --format json` example showed `coverage.pending`, `coverage.stale`, and target digest drift while `next_required_action` was `run_verify_fixes`. That tells external orchestrators to verify fixed findings even though the review universe is not current.

This is the same class of coverage-priority failure as confirmed findings, but for `fixed_pending_verification`. The status/ready contract needs to state and test that incomplete coverage and target digest drift outrank all finding work, including fix verification.

## Proposed Solution

Extend the existing review-session status/ready coverage-priority behavior so `pending`, `stale`, or target digest drift always result in review-oriented work before `run_verify_fixes`. Add regression tests for fixed-pending findings coexisting with pending/stale coverage and target digest drift. Repair `_next_action` or ready prompt selection if implementation drift is found.

## Acceptance Criteria

- `review-gauntlet status --format json` returns `next_required_action: run_review` when any review cell is `pending`, even if findings are `fixed_pending_verification`.
- `review-gauntlet status --format json` returns `next_required_action: run_review` when any review cell is `stale`, even if findings are `fixed_pending_verification`.
- `review-gauntlet status --format json` returns `next_required_action: run_review` when target digest drift exists, even if findings are `fixed_pending_verification`.
- `finalize_blockers` continues to include coverage blockers, target digest drift, and fixed-finding verification blockers together.
- `review-gauntlet ready --format json` prompts for review coverage or digest-drift review before fixed-finding verification whenever both are present.
- Existing behavior remains `run_verify_fixes` when coverage is current, no target digest drift exists, and fixed-pending findings are the highest-priority remaining work.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` deterministically checks pending/stale coverage and target digest drift before `fixed_pending_verification`.
- Unit tests cover pending-plus-fixed-pending, stale-plus-fixed-pending, and digest-drift-plus-fixed-pending status cases.
- Unit tests cover ready prompt precedence for at least one incomplete-coverage-plus-fixed-pending case.
- Existing fixed-pending verification workflows still pass when coverage is otherwise complete.
- `make check` passes.

## Out of Scope

- Changing fixed finding verification semantics.
- Automatically running review or verify-fixes loops.
- Changing dirty working tree blocker policy.
- Changing external orchestrator code outside review-gauntlet status/ready outputs.
