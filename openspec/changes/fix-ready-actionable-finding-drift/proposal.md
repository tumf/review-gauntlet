---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli_ready.py
  - tests/test_cli_run.py
  - openspec/specs/review-sessions/spec.md
---

# Fix ready/run actionable finding drift

**Change Type**: implementation

## Problem / Context

`review-gauntlet ready` can currently decide that a finding prompt is required from aggregate `finding_counts`, then fail while building the prompt because the materialized ready finding list contains no finding in that state. The observed failure was a confirmed-finding ready prompt path where `target_findings` was empty and `_first_file_path_from_findings()` raised `RuntimeError: ready prompt requested findings but none were actionable`.

When the same failure occurs during `review-gauntlet run`, command handling can continue with `result = None` and then raise `TypeError: 'NoneType' object is not subscriptable` while checking `result["completed"]`. That second error hides the actionable root cause from the developer and makes the session harder to recover.

This conflicts with the session product principle that unknown or incomplete work must remain visible, not crash into an unrelated traceback.

## Proposed Solution

Make ready-prompt selection use the same concrete actionable objects that will be rendered into the prompt. Aggregate state counts may continue to inform status and finalize blockers, but `ready` should not call a file-scoped finding prompt builder unless at least one non-terminal `_ReadyFinding` exists for that exact state.

Make `run` command result handling resilient to unexpected controller or ready-prompt failures so it never masks the primary failure with a secondary `None` indexing error. The command should either emit a structured failed run result when it can safely do so, or re-raise the original exception without replacing it with an unrelated error.

## Acceptance Criteria

- `review-gauntlet ready --format json` does not raise `RuntimeError` when aggregate finding counts mention an actionable state but the ready finding list has no renderable finding for that state.
- `ready` selects finding prompts from materialized findings and skips empty actionable-state buckets rather than constructing an impossible file-scoped task.
- `ready` preserves existing priority order when materialized review cells and findings are present: pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, stale review cells, finalize.
- `review-gauntlet run --format json` does not replace an underlying ready/controller exception with `TypeError: 'NoneType' object is not subscriptable`.
- The user-facing failure remains actionable and does not falsely imply successful completion.
- Existing file-scoped ready prompt behavior and same-prompt handoff from `ready` to `run` are preserved.

## Explicit Completion Conditions

This proposal is complete when repository evidence shows all of the following:

- `src/review_gauntlet/cli.py` chooses finding-ready prompts only from materialized actionable `_ReadyFinding` records for the selected state.
- `src/review_gauntlet/cli.py` handles `_cmd_run()` exceptional or absent results without a secondary `None` subscript failure.
- `tests/test_cli_ready.py` covers a drift case where DB finding counts and renderable ready findings disagree, and verifies `ready` returns the next valid prompt or `null` rather than tracebacking.
- `tests/test_cli_run.py` covers the run-command failure path and verifies the original failure is not masked by a `NoneType` indexing error.
- Existing ready prompt priority and file-scoped prompt tests continue to pass.
- `make check` passes.

## Out of Scope

- Changing finding state transition semantics.
- Changing terminal finding definitions.
- Changing the file-scoped prompt format beyond what is necessary to avoid empty target selection.
- Adding automatic repair or mutation of corrupted ledger rows.
- Changing TUI presentation beyond avoiding masked run-command failures.
