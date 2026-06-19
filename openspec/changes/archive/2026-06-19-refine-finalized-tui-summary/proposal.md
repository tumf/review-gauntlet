---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/coverage_projection.py
  - tests/test_run_tui.py
  - openspec/specs/run-controller/spec.md
---

# Refine Finalized TUI Summary

**Change Type**: implementation

## Premise / Context

- `review-gauntlet run` replaces the operational TUI panels with a `Finalized summary` panel when the run/session reaches finalized state.
- The current finalized summary is derived in `src/review_gauntlet/run_tui.py` from `RunSnapshot.coverage_projection` and displays coverage, checkpoint, resolved files, rules, and finding IDs.
- Current `resolved_files` means files whose coverage summary is fully reviewed, not files changed since review.
- Current finalized finding IDs can include dismissed, false-positive, waived, accepted-risk, confirmed, or non-actionable findings, which is broader than the requested “修正もの” display.
- `coverage_projection.QueueEntry.changed_since_review` already records file-level change detection for TUI prioritization.
- The constitution requires incompleteness and decisions to stay explicit, so the summary must not imply non-fixed or non-changed items were fixed.

## Problem / Context

The finalized TUI summary currently mixes completion, decision, and modification concepts. A completed review cell can cause a file to appear under `Resolved files` even when the file was not changed, and a finding can appear in `Finding IDs` even when it was dismissed, accepted as risk, waived, or merely confirmed. This makes the final run summary less useful for users who want the final TUI to highlight only the files that changed during the session and only the findings that were actually fixed or pending verification.

## Proposed Solution

Refine the finalized summary derivation and rendering so the finalized panel focuses on changed-file fix outcomes:

- Derive `changed_files` from `coverage_projection.queue` entries with `changed_since_review == True`, de-duplicate them, and render only those files in the finalized summary.
- Rename the display label from `Resolved files` to `Changed files` to avoid conflating coverage completion with file modification.
- Derive finalized `finding_ids` only from findings whose `file_path` is in the changed-file set and whose state is `fixed_pending_verification` or `fixed_verified`.
- Render the fixed finding count from that filtered finding set rather than from broad terminal/decision counts.
- Render rules from the filtered fixed findings so the rule list matches the displayed finding IDs.
- Preserve existing finalized panel replacement behavior, coverage/checkpoint/run metadata, and non-finalized operational panels.

## Acceptance Criteria

- When finalized TUI rendering receives a projection with changed and unchanged files, the finalized summary lists only files whose queue entries have `changed_since_review == True`.
- When there are no changed files, the finalized summary renders an explicit empty value such as `none` rather than listing fully reviewed but unchanged files.
- The finalized summary finding count and finding IDs include only findings on changed files whose state is `fixed_pending_verification` or `fixed_verified`.
- Findings in `confirmed`, `dismissed`, `false_positive`, `accepted_risk`, `waived`, `open`, or `untriaged` do not appear in the finalized fixed finding list.
- Fixed findings on unchanged files do not appear in the finalized fixed finding list.
- The finalized summary rule list is limited to rules represented by the displayed fixed findings.
- Compact finalized output and Rich TUI finalized rendering use the same filtered summary data.
- Existing finalized/non-finalized panel visibility behavior remains unchanged.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/run_tui.py` derives finalized changed files from `QueueEntry.changed_since_review` rather than fully reviewed file summaries.
- `src/review_gauntlet/run_tui.py` derives finalized finding IDs and fixed finding count from changed-file findings in `fixed_pending_verification` or `fixed_verified` states only.
- `finalized_summary_tui_lines()` renders labels and values that match changed-file/fixed-finding semantics.
- `tests/test_run_tui.py` covers changed-file filtering, fixed-finding filtering, excluded terminal/non-fixed states, and compact/finalized summary text behavior.
- `make check` passes.

## Out of Scope

- Changing review, resolve, mark, or finalize state-machine semantics.
- Adding new finding states or changing allowed transitions.
- Changing queue prioritization or files/rules hotlist behavior outside finalized summary rendering.
- Changing checkpoint generation or persisted session ledger schema.
