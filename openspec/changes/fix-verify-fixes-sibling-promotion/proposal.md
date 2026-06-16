---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - tests/test_cli_ready.py
  - tests/test_cli_verify_fixes.py
  - openspec/changes/archive/2026-06-14-prioritize-pending-before-findings/proposal.md
  - openspec/changes/archive/2026-06-14-enforce-review-before-verification/proposal.md
---

# Fix verify-fixes sibling cell promotion disrupting run loop

**Change Type**: implementation

## Problem / Context

`review-gauntlet run` starts a review when `ready` and `status` both indicate `run_verify_fixes`. The root cause is in `_cmd_verify_fixes` (cli.py:1057): after evaluating a cell, `refresh_file_digest(stale_to_pending=True)` promotes STALE sibling cells on the same file path to PENDING. Since `_ready_prompt()` checks PENDING before fixed-pending-verification (cli.py:1353), the next run loop iteration selects a review prompt instead of continuing verify-fixes work.

This breaks the run orchestrator contract: the run loop should continue verifying fixed findings until all fixed-pending findings are resolved before moving to review coverage work.

Additionally, the canonical spec scenario at spec.md:653 lists the ready prompt priority as `stale, pending, reopened, untriaged, confirmed, FPV, finalize`, but the implemented and tested priority is `pending, reopened, untriaged, confirmed, FPV, stale, finalize`. The implemented ordering was established by archived proposal `prioritize-pending-before-findings` (2026-06-14) which intentionally moved stale after finding work to avoid redundant review passes during fix cycles.

## Proposed Solution

1. Change `_cmd_verify_fixes` to call `refresh_file_digest(stale_to_pending=False)` so sibling cells keep their persisted state with updated content digest instead of being promoted to PENDING.
2. Update the canonical spec scenario at spec.md:653 to match the implemented priority order.
3. Update the verify-fixes sibling freshness scenario at spec.md:507-515 to explicitly prohibit sibling promotion to PENDING.
4. Remove the unused `current_coverage_requires_review` parameter from `_next_action()`.

## Acceptance Criteria

- After `verify-fixes` evaluates a cell, STALE sibling cells on the same path retain STALE state with updated content digest; they are NOT promoted to PENDING.
- `review-gauntlet run` continues issuing verify-fixes prompts as long as fixed-pending-verification findings remain and no higher-priority work (pending cells, untriaged/reopened/confirmed findings) exists.
- The canonical ready prompt priority scenario matches the implemented code ordering: pending, reopened, untriaged, confirmed, FPV, stale, finalize.
- `_next_action()` no longer accepts the unused `current_coverage_requires_review` parameter.
- `make check` passes.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` line ~1057: `stale_to_pending=False` in `_cmd_verify_fixes`.
- `src/review_gauntlet/cli.py` `_next_action()`: signature and call site updated to remove `current_coverage_requires_review`.
- `openspec/specs/review-sessions/spec.md` scenario "Ready prompt priority is deterministic" lists the implemented order.
- `openspec/specs/review-sessions/spec.md` scenario "Verify fixes refreshes targeted path sibling freshness" states siblings are not promoted to PENDING.
- At least one unit test verifies that after `verify-fixes`, sibling cells remain STALE (not PENDING).
- At least one unit test verifies that `_ready_prompt()` returns a verify-fixes prompt when STALE sibling cells coexist with fixed-pending findings.
- `make check` passes with no regressions.

## Out of Scope

- Changing the `review` command's `stale_to_pending=True` behavior (correct for review).
- Changing finding state transitions or verification semantics.
- Changing the TUI gate sequential model or `select_active_gate` behavior.
- Changing finalization requirements.
