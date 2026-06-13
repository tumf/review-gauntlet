---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli_ready.py
  - openspec/specs/review-sessions/spec.md
---

# Treat target digest drift as review-ready work

**Change Type**: implementation

## Problem / Context

`review-gauntlet status` can detect that the current target digest differs from the digest recorded by the last completed review run. However, `status` intentionally reads ledger state and does not reconcile review cells into `stale`. In this intermediate state, `status` reports `target digest has changed since the last review run` but may still report all cells as `reviewed`, and `ready` can return `no ready task` even though the correct next action is to run review work.

The desired behavior is B+C from the design discussion: keep `status` and `ready` read-only, but treat target digest drift as review work when computing `next_required_action` and ready prompts.

## Proposed Solution

Update action selection so `target digest has changed since the last review run` maps to `run_review` even before cell reconciliation persists stale states. Update `ready` so the same blocker is considered actionable and returns a review prompt, without mutating review cell state, finding state, checkpoint files, or git state.

The change should preserve existing stale-cell behavior: when stale cells are already persisted, `ready` continues to return the stale review prompt. When stale cells are not yet persisted but target digest drift is present, `ready` returns a review-oriented prompt rather than `no ready task`.

## Acceptance Criteria

- `review-gauntlet status` remains read-only and does not call reconciliation solely to update persisted cell states.
- When finalization is blocked by `target digest has changed since the last review run`, `status` reports `next_required_action: run_review` unless a higher-priority finding or cell action already applies.
- When review/finding work appears complete in the ledger but finalization is blocked by target digest drift, `review-gauntlet ready` emits a review-oriented prompt and exits `0`.
- `ready` does not write checkpoint files, mutate session ledger rows, or stage/commit files while deriving that prompt.
- Dirty-git finalize behavior remains unchanged: dirty-only blockers still produce the commit/finalize prompt from the prior change.
- True non-actionable finalize blockers that are neither dirty-git nor target-digest drift continue to produce `no ready task` and exit `1`.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` treats the exact target-digest drift blocker as a review action in `_next_action` or an equivalent helper.
- `src/review_gauntlet/cli.py` treats the same blocker as actionable for `_ready_prompt` without calling `_reconcile_cells` from `ready` or `status`.
- `tests/test_cli_ready.py` or another focused CLI test proves `ready` returns a review prompt for target digest drift before persisted stale cell state exists.
- CLI status tests prove `next_required_action` is `run_review` for the same drift-only state.
- `make check` passes.

## Out of Scope

- Do not make `status` or `ready` persist stale cell updates.
- Do not change how `review` or `verify-fixes` reconcile cells.
- Do not change target digest computation or review universe inclusion rules.
- Do not automatically run review, finalize, stage, or commit from `ready` or `status`.
