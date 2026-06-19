---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
  - openspec/specs/run-controller/spec.md
---

# Add TUI Color Legend

**Change Type**: implementation

## Premise / Context

- The inferred request is to make `review-gauntlet run`'s TUI legend show the same color categories used by the TUI body.
- Current TUI rendering is centralized in `src/review_gauntlet/run_tui.py`, where `TuiField.color` is rendered through Rich in `render_tui_lines()`.
- The existing `color_legend_tui_lines()` only shows `done / find` in `_FIND_COUNT_COLOR`, while body panels already use `_PRIORITY_COLORS`, `_FINDING_STATE_COLORS`, `_ACTIVITY_LABEL_COLORS`, `_STATE_COLORS`, `_RULE_ID_COLOR`, `_FINDING_ID_COLOR`, and `_FIND_COUNT_COLOR`.
- The repo constitution requires explicit visibility for unreviewed/open/undecided states, so the legend must help users interpret state and priority color without hiding incomplete work.
- Existing TUI behavior is covered by `tests/test_run_tui.py`; project verification is `make check`.

## Requested Artifact

Implementation.

## Problem / Context

The run TUI uses color to communicate priority, finding state, activity, and progress, but the legend currently documents only the `done / find` finding-count color. Users must infer the meaning of other colored body text from context, which makes the TUI less explicit and undermines the goal of making review state visible.

## Proposed Solution

Expand the run TUI legend so it displays compact, color-coded samples for the primary body color categories that users need to interpret during a run:

- Priority labels: `P0`, `P1`, `P2`, `P3`, using `_PRIORITY_COLORS`.
- Finding states: `open`, `confirmed`, `dismissed`, using `_FINDING_STATE_COLORS`.
- Finding progress labels: `done` and `find`, using `_FIND_COUNT_COLOR`.

Keep the implementation minimal by reusing existing color maps and `TuiLine`/`TuiField` helpers. The body panels should continue to use the same color constants already used by the legend, avoiding duplicate hard-coded style values.

## Acceptance Criteria

- The run TUI legend renders visible samples for `P0`, `P1`, `P2`, `P3`, `open`, `confirmed`, `dismissed`, `done`, and `find`.
- Each legend sample uses the same color source used by the corresponding TUI body content.
- Existing body content retains its current color semantics for queue/rules/files priorities, finding states, and finding progress.
- Plain-text rendering of the legend remains readable and deterministic for tests and non-Rich output.
- The change does not alter run-controller behavior, review progression, adapter invocation, or persisted session state.

## Explicit Completion Conditions

The change is complete when:

- `src/review_gauntlet/run_tui.py` updates `color_legend_tui_lines()` to include the listed legend samples using existing color constants/maps.
- `tests/test_run_tui.py` verifies the expanded legend text and, where practical, the corresponding Rich field colors or `TuiField.color` values.
- Focused TUI tests pass with `uv run pytest tests/test_run_tui.py`.
- Repository checks pass with `make check`.
- `cflx openspec validate add-tui-color-legend --strict --evidence warn` passes for this proposal.

## Out of Scope

- Redesigning the TUI layout or adding new panels.
- Changing the meaning of existing priority, finding-state, activity, cell-state, rule-id, finding-id, or count colors.
- Adding user-configurable themes.
- Changing non-TUI `review-gauntlet run --no-tui` output.
