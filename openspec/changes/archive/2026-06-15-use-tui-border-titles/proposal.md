---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
  - openspec/specs/review-sessions/spec.md
---

# Use Textual Border Titles for Run TUI Panels

**Change Type**: implementation

## Premise / Context

- `review-gauntlet run` has an optional Textual TUI implemented in `src/review_gauntlet/run_tui.py`.
- Current TUI panel labels such as `Activity`, `Finalize path`, `Session metrics`, `Findings`, and `Current operation` are rendered as the first line of `Static` body text.
- The existing canonical `review-sessions` spec already defines the run TUI as a Textual dashboard with named regions and semantic panel styling.
- Repository guidance requires Python 3.11, strict Pyright, Ruff, tests under `tests/`, and CI-equivalent verification via `make check`.

## Problem / Context

The TUI visually represents dashboard sections as bordered panels, but their titles are currently part of each panel body. This wastes vertical space, makes the rendered output look less like a titled dashboard panel, and couples plain-text section helpers to Textual presentation concerns. Activity should appear embedded in the panel border, not as the first row of activity content.

## Proposed Solution

Refactor the run TUI so panel section names are assigned through Textual border titles on widgets or containers that already have borders. Use a small reusable titled-pane structure for dashboard panels and keep body text helpers focused on panel contents. Preserve text-mode or compact summary coverage by adding explicit titled-section helpers where non-Textual output still needs section labels.

The change should apply consistently to the visible dashboard panels rather than only to Activity, so the TUI uses one coherent visual pattern for panel headings.

## Acceptance Criteria

- The interactive Textual `run` TUI renders section names as `border_title` values for titled dashboard panels.
- `Activity` is no longer emitted as the first line of the activity body text used inside the Textual panel.
- `Finalize path`, `Session metrics`, `Findings`, and `Current operation` are likewise removed from panel body text in the interactive TUI and rendered as border titles instead.
- Border titles inherit semantic styling that remains compatible with existing normal, active, blocked, failed, and finalized panel states.
- Plain text helpers or compact test summaries that intentionally need section names still have an explicit way to include those section names without reintroducing body-heading rows into the TUI.
- Existing run semantics, task selection, command execution, JSON output, non-TUI behavior, and fallback behavior remain unchanged.

## Explicit Completion Conditions

- `src/review_gauntlet/run_tui.py` defines and uses a reusable Textual titled-pane/container or equivalent helper so panel titles are assigned through `border_title`.
- The TUI compose/update paths keep updating the correct body `Static` widgets while applying semantic state classes to the bordered titled panels.
- `activity_text()` and the other panel body helpers no longer include their section title as the first body line for Textual panel content.
- `tests/test_run_tui.py` includes regression coverage proving activity body text omits `Activity`, compact/text section rendering can still include titles when intended, and source/CSS expectations remain valid.
- `make check` passes.

## Out of Scope

- Replacing Textual with Rich `Panel` rendering.
- Changing run orchestration, adapter execution, session persistence, or finalization semantics.
- Redesigning the entire TUI layout beyond moving panel headings into border titles.
- Adding new commands or changing CLI arguments.
