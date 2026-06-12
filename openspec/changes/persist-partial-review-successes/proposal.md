---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli_session_review.py
  - tests/test_review_progress.py
  - openspec/specs/review-sessions/spec.md
  - openspec/CONSTITUTION.md
---

# Persist Partial Review Successes

**Change Type**: implementation

## Problem/Context

`review-gauntlet review --budget 5` can execute selected cells concurrently and report several per-cell successes, but still emit `reviewed_cells: 0` and leave coverage unchanged when an earlier selected cell fails. The observed run selected five cells, four completed successfully, and the first selected `uv.lock` cell failed because its verdict file was missing. Since `_cmd_review()` processes results in `selected_cells` order and exits immediately on the first failure, later successful results are never recorded in the ledger.

This breaks the coverage contract. The constitution states that reviewed coverage is a first-class product and that `reviewed` means the defined target was executed with the defined rule. A failed sibling cell must not erase successful work already completed in the same one-step review run.

## Proposed Solution

Change review result finalization so every successful selected cell is persisted before the command exits for any failed selected cell. The command should still return a non-zero exit code when any selected cell fails, and failed or unfinished cells must remain non-reviewed. The final output for a failed run should include the number of successful cells that were persisted, the failed cell id/error details, finding ids recorded from successes, and current status after those partial successes are saved.

Keep the one-run semantics: the command must not retry failed cells, select replacement cells, or auto-loop to completion.

## Acceptance Criteria

- If a review run has both successful and failed selected cells, all successful cells from that run are marked reviewed and have their findings/occurrences recorded before the command exits.
- The failed run still exits non-zero and reports `failed_cell_id`, `error`, and `failure` for at least one failed cell.
- The failed or unfinished cell remains pending/stale/non-reviewed and can be selected again by a later review run.
- `reviewed_cells` in the failed final output reflects the number of successful cells persisted from that run, independent of selected-cell ordering.
- Fixed-finding verification uses the paths that were successfully evaluated in the partial run, while failed paths do not verify fixes.
- Successful review result processing remains deterministic and does not depend on thread completion order for IDs, counts, or persisted states.
- Existing all-success review behavior and interrupt/cancellation behavior remain compatible.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` processes and persists successful `ReviewAdapterResult` values even when one or more selected cells produced `ReviewAdapterError`.
- The failed-run output is generated after partial successes are saved and `_status()` reflects the updated coverage.
- A regression test proves a selected-cell-order failure does not discard later successful results.
- A regression test proves failed cells remain non-reviewed after a partial run.
- A regression test proves fixed-finding verification is applied only for successfully evaluated paths in a partial run.
- Focused CLI review tests pass.
- `make check` passes.
- `cflx openspec validate persist-partial-review-successes --strict` passes.

## Out of Scope

- Retrying failed cells automatically.
- Changing adapter timeout, verdict-file generation, command adapter output paths, or prompt content.
- Changing review cell selection order or budget semantics.
- Changing finding triage transitions outside fixed-finding verification for successfully evaluated paths.
- Adding a new durable run state model beyond persisting successful cells and returning failure for failed cells.
