---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/targets.py
  - tests/test_cli_ready.py
  - openspec/specs/review-sessions/spec.md
---

# Fix status action for target digest drift

**Change Type**: implementation

## Problem / Context

`review-gauntlet status` can report `coverage: {'reviewed': ...}` while still returning `next_required_action: run_review` solely because the current whole-review-universe target digest differs from the last run digest. In sessions where all current review cells are already reviewed and findings remain `fixed_pending_verification`, this misdirects agents toward another review run instead of the required fix verification.

The existing canonical spec requires target digest drift to map to review work. That behavior is too broad: digest drift is a freshness signal, but it should not override more precise current-cell coverage evidence when no current review cell is pending, stale, or missing.

## Proposed Solution

Update session status and ready-action selection so target digest drift only forces review work when it corresponds to incomplete current review coverage. The implementation should evaluate current target cells against persisted session cells without mutating ledger state during `status` or `ready`.

When every current target cell exists in the session ledger, has a matching content digest, and is already reviewed, `status` should allow normal finding-state priority to proceed. In that case, fixed-pending findings should produce `next_required_action: run_verify_fixes` even if the whole target digest differs from the last run digest.

Dirty working tree and digest drift may remain visible as finalize blockers where appropriate, but they must not misclassify the next actionable step as review work unless current review coverage is actually incomplete.

## Acceptance Criteria

- `status` returns `run_review` when current review cells are pending, stale, or missing from the session ledger.
- `status` does not return `run_review` solely because whole-target digest drift exists when all current review cells are reviewed with matching content digests.
- If all current review cells are reviewed and findings are `fixed_pending_verification`, `status` returns `run_verify_fixes`.
- `ready` mirrors the corrected action priority and prompts for fixed-finding verification instead of digest-drift review work in the same complete-coverage case.
- `status` and `ready` remain non-mutating for review cell and finding ledger state.
- Finalization still refuses to finalize over unresolved dirty/freshness blockers unless the implementation explicitly records that those blockers are not applicable to the current reviewed target.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` computes current-cell freshness for status/ready action selection without mutating persisted review cell state.
- Regression tests cover complete reviewed coverage plus fixed-pending findings plus unrelated target digest drift, and assert `run_verify_fixes`.
- Existing tests for pending and stale cells still assert `run_review` priority.
- Spec delta under `openspec/changes/fix-status-digest-drift-action/specs/review-sessions/spec.md` validates with strict OpenSpec validation.
- Project checks pass with `make check` or the focused tests plus lint/typecheck if full checks are impractical.

## Out of Scope

- Changing the meaning of `reviewed` to imply code safety.
- Auto-running review or verification loops.
- Automatically committing or reverting dirty working tree files.
- Removing the target digest from run records or checkpoints.
