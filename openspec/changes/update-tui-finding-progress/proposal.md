---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/coverage_projection.py
  - tests/test_run_tui.py
  - openspec/specs/run-controller/spec.md
  - openspec/specs/review-sessions/spec.md
---

# Update TUI Finding Progress

**Change Type**: implementation

## Problem / Context

The `review-gauntlet run` TUI cells view currently renders per-cell finding progress as `findings {actionable}/{total}` via `run_tui._format_cell_entry()`. Because other progress displays use completed work over total work, this makes `findings 2/5` look like a completion ratio even though the numerator is unresolved actionable findings.

This conflicts with the product principle that unresolved and resolved review state must remain explicit. The TUI should show how many findings attached to a cell are resolved out of the total findings attached to that cell.

## Proposed Solution

Change the cells view finding progress display to render resolved findings over total findings:

```text
findings {resolved_finding_count}/{finding_count} resolved
```

`resolved_finding_count` SHALL count findings whose state is terminal according to the finding terminal-state model already used by review sessions. Existing actionable finding counts SHALL remain available for priority, queue ordering, and why/explanation text.

## Acceptance Criteria

- Cells view entries in `review-gauntlet run` show finding progress as resolved findings over total findings.
- The numerator counts terminal finding states, not actionable/open findings.
- The denominator remains the total number of findings attached to the cell.
- Priority, queue selection, and existing actionable-finding explanations continue to use actionable/open finding counts.
- Existing finalized-summary resolved finding behavior remains unchanged.

## Explicit Completion Conditions

- `coverage_projection.QueueEntry` or equivalent projection data exposes resolved finding count per cell.
- `coverage_projection._queue_entry_for_cell()` or equivalent projection construction computes resolved count from finding states rather than deriving it in the renderer from display text.
- `run_tui._format_cell_entry()` renders `findings {resolved}/{total} resolved` for cell entries.
- Tests cover at least one mixed finding-state cell where open and terminal findings produce a resolved-over-total display.
- Repository checks pass with `make check`.

## Out of Scope

- Changing file hotlist or rule summary wording unless needed for compatibility with the new projection field.
- Changing finding state transitions, resolve semantics, or finalize blockers.
- Removing actionable finding counts from prioritization or queue explanations.
