---
change_type: implementation
priority: medium
dependencies: []
references:
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
---

# Rename run TUI finalize checklist panel

**Change Type**: implementation

## Problem / Context

The `review-gauntlet run` TUI currently titles its primary progress panel `Next to finalize`. The panel does not show a single next action; it shows the full ordered finalize readiness checklist with six rows: Review coverage, Triage findings, Fix confirmed findings, Verify fixes, Final checks, and Finalize checkpoint.

That wording is misleading because:

- `Next to finalize` reads like one next item rather than a checklist title.
- The body is generated from `finalize_path_text(view)` and represents all finalize gates.
- The canonical `review-sessions` spec currently hard-codes `Next to finalize`, so the spec, implementation, and tests must move together.

## Proposed Solution

Rename the primary run TUI progress panel from `Next to finalize` to `Finalize checklist` everywhere it is user-visible.

The panel body and gate derivation stay unchanged. The TUI continues to render the same six ordered rows and the same state labels, blocker classification, header gate label, Agent summary, Session summary, Activity timeline, command behavior, JSON behavior, non-TUI behavior, and finalization semantics.

## Acceptance Criteria

- Interactive `review-gauntlet run` TUI displays the primary progress panel title as `Finalize checklist`.
- Compact dashboard text displays `Finalize checklist` in the corresponding section.
- The rendered dashboard no longer displays `Next to finalize` as a panel or section title.
- The checklist still renders the existing six ordered rows with their existing state labels and details.
- Header status, Agent panel, Session panel, Activity panel, task selection, command execution, JSON output, non-TUI fallback behavior, and session finalization behavior remain unchanged.
- The canonical `review-sessions` spec delta describes the new panel title so implementation and tracked behavior are aligned.

## Explicit Completion Conditions

This change is complete when:

- `src/review_gauntlet/run_tui.py` uses `Finalize checklist` for `PANEL_TITLES["finalize_path"]` or its equivalent shared title source.
- `tests/test_run_tui.py` asserts that compact/TUI dashboard text contains `Finalize checklist` and does not contain `Next to finalize` as the progress panel title.
- Existing tests still verify that the six rows remain Review coverage, Triage findings, Fix confirmed findings, Verify fixes, Final checks, and Finalize checkpoint.
- The `review-sessions` spec delta modifies the existing run TUI dashboard requirement to require `Finalize checklist` instead of `Next to finalize`.
- `uv run pytest tests/test_run_tui.py` passes.
- `make check` passes, or any failure is unrelated and documented with evidence.

## Out of Scope

- Changing checklist row names, ordering, state derivation, blocker classification, or row details.
- Reintroducing the old `Finalize path` panel label.
- Changing Textual layout, panel ordering, border-title behavior, or color/styling rules.
- Changing command execution, timeout handling, JSON output, non-TUI output semantics outside the compact dashboard heading, or finalization semantics.
