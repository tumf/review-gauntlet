---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli_ready.py
  - openspec/specs/review-sessions/spec.md
---

# Guide ready users to commit dirty finalize blockers

**Change Type**: implementation

## Problem / Context

`review-gauntlet ready` is the handoff surface used by external orchestrators to decide the next continuation action. When review coverage and finding state are complete but finalization is blocked only because the working tree has dirty files that must be committed, `status` correctly reports `next_required_action: resolve_finalize_blockers`, but `ready` currently returns no prompt. This leaves an otherwise actionable state indistinguishable from a true no-op state.

The observed session state has all cells reviewed and all findings terminal, while finalize is blocked by dirty review-universe and non-review files. In that state, the next useful agent action is to commit intended changes before finalizing.

## Proposed Solution

Update `review-gauntlet ready` so that after review/finding work is exhausted, dirty-git finalize blockers produce a short skill-directed prompt instructing the agent to commit intended git changes and then finalize. Preserve `no ready task` for blockers that are not resolved by committing, such as missing review-run evidence or changed target digests requiring review work.

## Acceptance Criteria

- When an active session has no pending/stale review cells and no non-terminal findings, but finalization is blocked only by dirty review-universe and/or non-review working-tree paths, `review-gauntlet ready` emits a non-null prompt and exits `0`.
- The dirty-finalize prompt tells the agent to commit intended git changes before finalizing the session.
- `ready` remains read-only and does not write checkpoint files, mutate session ledger rows, or stage/commit files itself.
- `ready` continues to return `no ready task` with exit `1` when remaining finalize blockers are not commit-resolvable.
- Existing priority ordering remains unchanged: reopened, untriaged, confirmed, fixed-pending verification, stale cells, and pending cells still take precedence over dirty-finalize prompts.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` contains logic that distinguishes commit-resolvable dirty finalize blockers from non-commit-resolvable blockers in `_ready_prompt` or a narrowly scoped helper.
- `tests/test_cli_ready.py` contains regression coverage for dirty review-universe and non-review finalize blockers producing a commit/finalize ready prompt.
- `tests/test_cli_ready.py` continues to cover a non-commit-resolvable blocker returning `prompt: null` and exit `1`.
- `make check` passes.

## Out of Scope

- `ready` must not perform git commits, staging, finalization, or checkpoint writes itself.
- This change does not alter `status` or `finalize` blocker semantics.
- This change does not add automatic review loops or change review/finding state transitions.
